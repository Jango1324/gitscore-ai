"""Milestone 9B Phase 2 -- retrieval-sensitive end-to-end evaluation.

M8E's own consolidated evaluation (`docs/evaluation/MILESTONE_8E_CONSOLIDATED_EVALUATION.md`
Section 3.1) found that job-aware repository retrieval (Milestone 8D.2)
expanded the analyzed repository set in 9 of the 12 existing
`evaluation/gold/matrix.json` pairs, yet changed `alignment_score` in
ZERO of them. That result does not prove retrieval has no value -- it
proves the existing 12-pair matrix, built for Milestone 8C's qualitative
positive/partial/negative spread, never contained a case where the
newly-recovered evidence was anything OTHER than redundant with evidence
already present generically.

This module runs the SAME real composition `analyze_job_fit()` uses
(`extract_candidate_evidence()` -> `match_job()` -> `assess_job()`),
twice per case -- once with job-aware retrieval, once without -- against
SYNTHETIC fixtures engineered specifically to separate four DISTINCT
events the brief requires kept apart:

  A. Retrieval success       -- was the target repository newly analyzed?
  B. New evidence discovery   -- did that repository's deep extraction
                                  produce a concept_id not already
                                  present anywhere in the generic-only
                                  evidence pool?
  C. New requirement support   -- did any requirement's MatchStatus
                                  actually flip to SUPPORTED as a result?
  D. Alignment-score impact    -- did assess_job()'s alignment_score (or
                                  the required/preferred subscores)
                                  actually change?

A case can have A=True, B=True, C=False, D=False (redundant recovery --
m9b_redundant_rust_01) just as easily as all four True (a genuine flip
-- m9b_rust_or_go_backend_01), or A=False entirely (a genuinely relevant
repository still crowded out of the fixed top-K budget --
m9b_kotlin_preferred_01). None of these four booleans is derived from
any other; each is measured independently from the real pipeline's own
output, never assumed from the others.
"""
from __future__ import annotations

from dataclasses import dataclass

from gitscore.application.job_fit import _relevance_terms_from_job_profile
from gitscore.assessment import assess_job
from gitscore.github.parser import parse_repo_summary
from gitscore.jobs import parse_job_description
from gitscore.matching import match_job
from gitscore.matching.types import MatchStatus
from gitscore.pipeline.evidence import extract_candidate_evidence
from gitscore.ranking.job_relevance import score_repository_relevance

from evaluation_lib.loaders import build_fake_client


@dataclass
class RetrievalSensitivityCase:
    job_id: str
    candidate: str
    test_intent: str

    generic_selected: tuple[str, ...]
    job_aware_selected: tuple[str, ...]
    job_relevant_additions: tuple[str, ...]

    retrieval_success: bool               # (A) was >=1 job-relevant addition made at all
    new_evidence_concepts: tuple[str, ...]  # (B) concept ids present job-aware but not generic
    newly_supported_requirements: tuple[str, ...]  # (C) requirement keys flipped NOT_OBSERVED/NOT_ASSESSABLE -> SUPPORTED
    still_not_observed: tuple[str, ...]
    not_assessable_count: int

    alignment_before: int | None          # (D)
    alignment_after: int | None
    required_before: tuple[int, int] | None
    required_after: tuple[int, int] | None
    preferred_before: tuple[int, int] | None
    preferred_after: tuple[int, int] | None
    score_changed: bool
    score_change_justified: bool
    justification_note: str


def _requirement_key(requirement) -> str:
    """A stable, human-readable key for one JobRequirement -- its own
    `original_text` is already unique per claim in these single-claim-
    per-bullet synthetic jobs, so no separate id scheme is needed.
    """
    return requirement.original_text


def _concept_ids_in_profile(profile) -> set[str]:
    return set(profile.concept_summaries.keys())


def _evaluate_one(job: dict, fixture: dict) -> RetrievalSensitivityCase:
    job_profile = parse_job_description(job["raw_text"], title=job.get("title"))
    relevance_terms = _relevance_terms_from_job_profile(job_profile)

    generic_client = build_fake_client(fixture)
    generic_result = extract_candidate_evidence(
        fixture["candidate"], client=generic_client, top_n=fixture["top_n"]
    )

    job_aware_client = build_fake_client(fixture)
    job_aware_result = extract_candidate_evidence(
        fixture["candidate"], client=job_aware_client, top_n=fixture["top_n"], job_relevance_terms=relevance_terms
    )

    generic_names = tuple(sorted(r.name for r in generic_result.profile.coverage.analyzed))
    job_aware_names = tuple(sorted(r.name for r in job_aware_result.profile.coverage.analyzed))
    additions = tuple(sorted(set(job_aware_names) - set(generic_names)))

    generic_concepts = _concept_ids_in_profile(generic_result.profile)
    job_aware_concepts = _concept_ids_in_profile(job_aware_result.profile)
    new_concepts = tuple(sorted(job_aware_concepts - generic_concepts))

    match_before = match_job(generic_result.profile, job_profile)
    assessment_before = assess_job(match_before)
    match_after = match_job(job_aware_result.profile, job_profile)
    assessment_after = assess_job(match_after)

    status_before = {_requirement_key(m.requirement): m.status for m in match_before.requirement_matches}
    status_after = {_requirement_key(m.requirement): m.status for m in match_after.requirement_matches}

    newly_supported = tuple(
        sorted(
            key for key, before in status_before.items()
            if before != MatchStatus.SUPPORTED and status_after.get(key) == MatchStatus.SUPPORTED
        )
    )
    still_not_observed = tuple(
        sorted(key for key, after in status_after.items() if after == MatchStatus.NOT_OBSERVED)
    )

    def _tier(assessment, tier_name):
        tier = getattr(assessment, tier_name)
        return (tier.supported, tier.assessable) if tier else None

    alignment_before = assessment_before.alignment_score
    alignment_after = assessment_after.alignment_score
    required_before = _tier(assessment_before, "required")
    required_after = _tier(assessment_after, "required")
    preferred_before = _tier(assessment_before, "preferred")
    preferred_after = _tier(assessment_after, "preferred")

    score_changed = (
        alignment_before != alignment_after
        or required_before != required_after
        or preferred_before != preferred_after
    )

    # A score change is "justified" iff it is fully explained by a real
    # requirement flip (newly_supported non-empty) -- never by anything
    # else (e.g. a coincidental re-ranking that shouldn't be possible
    # given match_job()/assess_job() are pure functions of the profile +
    # job_profile, but checked explicitly rather than assumed, per this
    # milestone's Phase 3 integrity concern about conflating different
    # events).
    if score_changed and newly_supported:
        justification_note = f"score change fully explained by newly-SUPPORTED requirement(s): {newly_supported}"
        justified = True
    elif score_changed and not newly_supported:
        justification_note = "UNEXPLAINED: score changed with no corresponding newly-SUPPORTED requirement -- integrity concern, investigate"
        justified = False
    elif not score_changed and newly_supported:
        justification_note = "UNEXPLAINED: a requirement newly flipped to SUPPORTED but the score did not move -- integrity concern, investigate"
        justified = False
    else:
        justification_note = "no score change and no new support -- consistent (redundant recovery or no recovery)"
        justified = True

    return RetrievalSensitivityCase(
        job_id=job["job_id"],
        candidate=fixture["candidate"],
        test_intent=job.get("test_intent", ""),
        generic_selected=generic_names,
        job_aware_selected=job_aware_names,
        job_relevant_additions=additions,
        retrieval_success=bool(additions),
        new_evidence_concepts=new_concepts,
        newly_supported_requirements=newly_supported,
        still_not_observed=still_not_observed,
        not_assessable_count=match_after.not_assessable_count,
        alignment_before=alignment_before,
        alignment_after=alignment_after,
        required_before=required_before,
        required_after=required_after,
        preferred_before=preferred_before,
        preferred_after=preferred_after,
        score_changed=score_changed,
        score_change_justified=justified,
        justification_note=justification_note,
    )


def evaluate_cases(jobs: dict[str, dict], fixtures_by_candidate: dict[str, dict]) -> list[RetrievalSensitivityCase]:
    cases = []
    for job in jobs.values():
        fixture = fixtures_by_candidate[job["candidate"]]
        cases.append(_evaluate_one(job, fixture))
    return cases


def star_dominance_check(job: dict, fixture: dict, *, popular_repo: str, ordinary_repo: str) -> dict:
    """Auxiliary check (Phase 2's 'common-language repository that should
    not dominate retrieval' scenario): confirms a repository with a huge
    star count scores EXACTLY the same job-relevance as an ordinary
    repository sharing the same single matched concept -- stars are not
    a `score_repository_relevance()` input at all (only the generic,
    job-independent `rank.py` ranking reads them), so this is a direct,
    measured confirmation of that architectural fact, not an assumption.
    """
    job_profile = parse_job_description(job["raw_text"], title=job.get("title"))
    terms = _relevance_terms_from_job_profile(job_profile)
    summaries = {s["name"]: s for s in (parse_repo_summary(r) for r in fixture["repos_raw"])}

    popular = score_repository_relevance(summaries[popular_repo], terms)
    ordinary = score_repository_relevance(summaries[ordinary_repo], terms)
    return {
        "popular_repo": popular_repo,
        "popular_repo_stars": summaries[popular_repo]["stars"],
        "popular_repo_relevance_score": popular.relevance_score,
        "ordinary_repo": ordinary_repo,
        "ordinary_repo_stars": summaries[ordinary_repo]["stars"],
        "ordinary_repo_relevance_score": ordinary.relevance_score,
        "scores_equal_despite_star_gap": popular.relevance_score == ordinary.relevance_score,
    }


def aggregate_metrics(cases: list[RetrievalSensitivityCase]) -> dict:
    return {
        "cases_evaluated": len(cases),
        "retrieval_successes": sum(1 for c in cases if c.retrieval_success),
        "cases_with_new_evidence": sum(1 for c in cases if c.new_evidence_concepts),
        "cases_with_new_requirement_support": sum(1 for c in cases if c.newly_supported_requirements),
        "cases_with_score_change": sum(1 for c in cases if c.score_changed),
        "cases_with_unjustified_score_behavior": sum(1 for c in cases if not c.score_change_justified),
    }
