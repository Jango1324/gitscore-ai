"""Milestone 8D.2 -- repository-retrieval evaluation.

Measures whether job-aware retrieval (`gitscore.ranking.job_relevance`)
recovers a genuinely job-relevant repository that Milestone 5B's frozen
generic ranking alone excludes, without flooding the deep-analysis set
with irrelevant additions. Runs the REAL
`extract_candidate_evidence()` + `parse_job_description()` pipeline
against this evaluation's own offline candidate fixtures and job corpus
-- the SAME inputs `scripts/evaluate_end_to_end.py` uses, but a
SEPARATE, additive report: `evaluate_end_to_end.py` itself is NOT
modified by this milestone and continues to call
`extract_candidate_evidence()` with no `job_relevance_terms` (the
job-independent default), so none of its published numbers change.

For each gold case (candidate x job x repository), this module runs
`extract_candidate_evidence()` TWICE for the same candidate against the
same offline fixture: once with no job context (the "generic-only"
baseline) and once with `job_relevance_terms` derived from the job's
REAL parsed `JobRequirementProfile` (via
`gitscore.application.job_fit._relevance_terms_from_job_profile` --
the exact function `analyze_job_fit()` itself uses, not a
reimplementation) -- then classifies the outcome.

RELEVANCE TRUTH vs. OBSERVED OUTCOME -- the one rule this module exists
to enforce (post-review correction; see
docs/evaluation/MILESTONE_8D2_JOB_AWARE_RETRIEVAL.md Section 6): a gold
case's `genuinely_relevant` ground truth is an INDEPENDENT judgment
about the repository's real relevance to the job, authored without
regard to whether the current implementation happens to recover it. It
is NEVER revised just because job-aware retrieval fails to recover a
genuinely relevant repository (that failure is a real, reportable
retrieval miss -- see `RETRIEVAL_MISSED_RELEVANT` below -- not evidence
that the repository was never relevant). `expected_analyzed` is a
SEPARATE, independent field: the CURRENT implementation's measured,
pinned outcome (a regression guard), which is allowed to diverge from
`genuinely_relevant`. `classify_retrieval_outcome()` turns the pair
`(genuinely_relevant, generic_analyzed, newly_recovered)` into one of
five MUTUALLY EXCLUSIVE outcomes that keep "missed relevant repository"
structurally distinct from "correct negative control" -- the two must
never be collapsed into one "negative/expect_recovered=false" bucket,
which is exactly the conflation the prior version of this file made.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from gitscore.application.job_fit import _relevance_terms_from_job_profile
from gitscore.jobs import parse_job_description
from gitscore.pipeline.evidence import extract_candidate_evidence

from evaluation_lib.loaders import build_fake_client

# --- repository-retrieval outcome classification ---------------------
# Five mutually exclusive, exhaustive outcomes over
# (genuinely_relevant, generic_analyzed, newly_recovered). The two
# RELEVANT outcomes that are NOT "recovered" (ALREADY_COVERED,
# MISSED_RELEVANT) and the two IRRELEVANT outcomes
# (CORRECTLY_EXCLUDED, FALSE_POSITIVE_ADDITION) are deliberately never
# merged into a shared "negative"/"correct" bucket -- see module
# docstring.
RETRIEVAL_RECOVERED = "RETRIEVAL_RECOVERED"
RETRIEVAL_ALREADY_COVERED = "RETRIEVAL_ALREADY_COVERED"
RETRIEVAL_MISSED_RELEVANT = "RETRIEVAL_MISSED_RELEVANT"
RETRIEVAL_CORRECTLY_EXCLUDED = "RETRIEVAL_CORRECTLY_EXCLUDED"
RETRIEVAL_FALSE_POSITIVE_ADDITION = "RETRIEVAL_FALSE_POSITIVE_ADDITION"


def classify_retrieval_outcome(*, genuinely_relevant: bool, generic_analyzed: bool, newly_recovered: bool) -> str:
    """Pure classification -- no pipeline call, no gold lookup -- so it
    can be pinned directly with synthetic booleans (see
    tests/test_evaluation_harness.py).

    `job_aware_analyzed` is always exactly `generic_analyzed or
    newly_recovered` (the deterministic-union semantics of
    `select_repositories()`: a repository is analyzed in the job-aware
    run iff the frozen generic ranking already included it OR job
    relevance newly added it) -- never passed in independently, so the
    three relevant-case branches and two irrelevant-case branches below
    stay exhaustive by construction.
    """
    job_aware_analyzed = generic_analyzed or newly_recovered
    if genuinely_relevant:
        if newly_recovered:
            return RETRIEVAL_RECOVERED
        if job_aware_analyzed:
            return RETRIEVAL_ALREADY_COVERED
        return RETRIEVAL_MISSED_RELEVANT
    return RETRIEVAL_FALSE_POSITIVE_ADDITION if newly_recovered else RETRIEVAL_CORRECTLY_EXCLUDED


@dataclass
class RetrievalCaseResult:
    candidate: str
    job_id: str
    repo: str
    genuinely_relevant: bool
    expected_analyzed: bool
    generic_analyzed: bool
    job_aware_analyzed: bool
    newly_recovered: bool
    outcome: str
    prediction_correct: bool  # regression pin only: job_aware_analyzed == expected_analyzed. NOT a relevance judgment.
    rationale: str


@dataclass
class RetrievalPairResult:
    """Aggregate, per candidate x job pair, every job-aware ADDITION
    beyond the generic selection -- surfaces any unexpected/unlisted
    addition a case-by-case view alone could miss (Part "Also verify
    NEGATIVE behavior").
    """

    candidate: str
    job_id: str
    generic_analyzed_count: int
    job_aware_analyzed_count: int
    job_aware_additions: tuple[str, ...]
    max_selected_observed: int


def _evaluate_case(case: dict, fixture: dict, job: dict) -> RetrievalCaseResult:
    client_generic = build_fake_client(fixture)
    client_job_aware = build_fake_client(fixture)
    top_n = fixture["top_n"]

    generic_result = extract_candidate_evidence(case["candidate"], client=client_generic, top_n=top_n)
    generic_names = {r.name for r in generic_result.profile.coverage.analyzed}

    job_profile = parse_job_description(job["raw_text"], title=job.get("title"))
    terms = _relevance_terms_from_job_profile(job_profile)
    job_aware_result = extract_candidate_evidence(
        case["candidate"], client=client_job_aware, top_n=top_n, job_relevance_terms=terms
    )
    job_aware_names = {r.name for r in job_aware_result.profile.coverage.analyzed}

    repo = case["repo"]
    generic_analyzed = repo in generic_names
    job_aware_analyzed = repo in job_aware_names
    newly_recovered = job_aware_analyzed and not generic_analyzed
    genuinely_relevant = case["genuinely_relevant"]
    expected_analyzed = case["expected_analyzed"]

    outcome = classify_retrieval_outcome(
        genuinely_relevant=genuinely_relevant, generic_analyzed=generic_analyzed, newly_recovered=newly_recovered
    )

    return RetrievalCaseResult(
        candidate=case["candidate"],
        job_id=case["job_id"],
        repo=repo,
        genuinely_relevant=genuinely_relevant,
        expected_analyzed=expected_analyzed,
        generic_analyzed=generic_analyzed,
        job_aware_analyzed=job_aware_analyzed,
        newly_recovered=newly_recovered,
        outcome=outcome,
        prediction_correct=(job_aware_analyzed == expected_analyzed),
        rationale=case.get("rationale", ""),
    )


def evaluate_cases(
    cases: list[dict], fixtures: dict[str, dict], jobs: dict[str, dict]
) -> list[RetrievalCaseResult]:
    return [_evaluate_case(case, fixtures[case["candidate"]], jobs[case["job_id"]]) for case in cases]


def evaluate_pairs(cases: list[dict], fixtures: dict[str, dict], jobs: dict[str, dict]) -> list[RetrievalPairResult]:
    """One result per DISTINCT (candidate, job_id) pair referenced by
    `cases`, independent of how many individual repo-level cases share
    that pair -- surfaces the FULL set of job-aware additions, including
    any not named by a specific gold case.
    """
    seen: dict[tuple[str, str], RetrievalPairResult] = {}
    for case in cases:
        key = (case["candidate"], case["job_id"])
        if key in seen:
            continue
        fixture = fixtures[case["candidate"]]
        job = jobs[case["job_id"]]
        top_n = fixture["top_n"]

        generic_result = extract_candidate_evidence(
            case["candidate"], client=build_fake_client(fixture), top_n=top_n
        )
        job_profile = parse_job_description(job["raw_text"], title=job.get("title"))
        terms = _relevance_terms_from_job_profile(job_profile)
        job_aware_result = extract_candidate_evidence(
            case["candidate"], client=build_fake_client(fixture), top_n=top_n, job_relevance_terms=terms
        )

        generic_names = {r.name for r in generic_result.profile.coverage.analyzed}
        job_aware_names = {r.name for r in job_aware_result.profile.coverage.analyzed}
        additions = tuple(sorted(job_aware_names - generic_names))

        seen[key] = RetrievalPairResult(
            candidate=case["candidate"],
            job_id=case["job_id"],
            generic_analyzed_count=len(generic_names),
            job_aware_analyzed_count=len(job_aware_names),
            job_aware_additions=additions,
            max_selected_observed=len(job_aware_names),
        )
    return list(seen.values())


def aggregate_metrics(case_results: list[RetrievalCaseResult]) -> dict:
    """Transparent counts, kept in the SAME three structurally separate
    buckets `classify_retrieval_outcome()` produces -- a relevant repo
    that was missed is reported under `relevant_missed`, never folded
    into `negative_control_cases` (Part 3's "keep genuine negative
    controls separate from positive recovery cases").
    """
    relevant_cases = [r for r in case_results if r.genuinely_relevant]
    negative_cases = [r for r in case_results if not r.genuinely_relevant]

    recovered = [r for r in relevant_cases if r.outcome == RETRIEVAL_RECOVERED]
    already_covered = [r for r in relevant_cases if r.outcome == RETRIEVAL_ALREADY_COVERED]
    missed = [r for r in relevant_cases if r.outcome == RETRIEVAL_MISSED_RELEVANT]
    correctly_excluded = [r for r in negative_cases if r.outcome == RETRIEVAL_CORRECTLY_EXCLUDED]
    false_positives = [r for r in negative_cases if r.outcome == RETRIEVAL_FALSE_POSITIVE_ADDITION]

    prediction_correct = [r for r in case_results if r.prediction_correct]

    return {
        "cases_evaluated": len(case_results),
        # Regression pin only -- whether the CURRENT measured outcome
        # still matches the previously-measured `expected_analyzed`
        # pin. Never a relevance judgment; see module docstring.
        "prediction_matches_expected": len(prediction_correct),
        "prediction_mismatches_expected": len(case_results) - len(prediction_correct),
        "genuinely_relevant_cases": len(relevant_cases),
        "relevant_recovered_by_job_awareness": len(recovered),
        "relevant_already_covered_by_generic_ranking": len(already_covered),
        "relevant_missed_despite_job_awareness": len(missed),
        "negative_control_cases": len(negative_cases),
        "negative_controls_correctly_excluded": len(correctly_excluded),
        "negative_controls_with_false_positive_addition": len(false_positives),
    }
