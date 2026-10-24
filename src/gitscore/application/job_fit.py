"""Milestone 7C -- end-to-end job-analysis orchestration.

    GitHub username                      raw job-description text
        |                                         |
        v                                         v
    extract_candidate_evidence()  <--terms--  parse_job_description()
    (gitscore.pipeline.evidence)     (8D.2)   (gitscore.jobs)
        |                                         |
        v                                         |
    CandidateEvidenceProfile  --------+------------+
                                        |
                                        v
                                  match_job()  (gitscore.matching)
                                        |
                                        v
                                 JobMatchAnalysis
                                        |
                                        v
                                  assess_job()  (gitscore.assessment)
                                        |
                                        v
                                  JobAssessment

This module COMPOSES the four already-existing pipeline stages above. It
introduces no new analysis logic, no new scoring semantics, and no new
domain schema -- every object it returns is produced by calling an
existing stage function exactly once and handing its output to the
next. See each stage's own package (`gitscore.pipeline.evidence`,
`gitscore.jobs`, `gitscore.matching`, `gitscore.assessment`) for what it
actually computes.

Milestone 8D.2 adds the one new edge in the diagram above: job parsing
now runs BEFORE evidence extraction not only for the fail-fast reason
described below, but because `_relevance_terms_from_job_profile()`
(this module) converts the parsed `JobRequirementProfile` into
`gitscore.ranking.job_relevance.JobRelevanceTerm`s and passes them into
`extract_candidate_evidence(..., job_relevance_terms=...)`, so repository
selection can also consider job relevance. This is still pure
composition, not new analysis logic: the actual relevance SCORING lives
in `gitscore.ranking.job_relevance`, not here.

Dependency direction: `gitscore.application` depends on
`gitscore.pipeline`, `gitscore.jobs`, `gitscore.matching`, and
`gitscore.assessment`. None of those packages import anything from
`gitscore.application` -- this is the one layer allowed to know about
all of them together, which is why the `JobRequirementProfile` ->
`JobRelevanceTerm` bridge (`_relevance_terms_from_job_profile`, below)
lives here rather than inside `gitscore.jobs` (which has no reason to
know retrieval/ranking exists) or `gitscore.ranking.job_relevance`
(which has no reason to know the job domain model exists) -- see that
module's own docstring for the full rationale.

External vs. deterministic boundary: `extract_candidate_evidence()` is
the ONLY stage here that performs GitHub I/O. `parse_job_description()`,
`match_job()`, and `assess_job()` are pure functions of their inputs --
given the same GitHub responses (as captured inside a
`CandidateEvidenceProfile`) and the same job text/title/company, they
produce byte-identical results every time, independent of how many
times or in what order this module is called.

Failure semantics: a blank `username` or `job_description` raises
`ValueError` before any network call is made. Every GitHub-side
exception (`GitHubNotFoundError`, `GitHubRateLimitError`,
`GitHubRequestError`) -- and every partial per-repository extraction
failure `extract_candidate_evidence()` already isolates -- propagates or
is surfaced UNCHANGED; this module adds no `except Exception` of its
own anywhere. A job description that parses to zero requirements, or a
candidate with zero GitHub evidence, is NOT a failure: `analyze_job_fit()`
returns a normal `JobAnalysisResult` whose `assessment.alignment_score`
is simply `None` -- see `gitscore.assessment.models.JobAssessment` for
why `None` (no assessable requirements) is a materially different fact
from `0` (assessed, and nothing was supported).
"""
from __future__ import annotations

from dataclasses import dataclass

from gitscore.assessment import JobAssessment, assess_job
from gitscore.evidence.profile import CandidateEvidenceProfile
from gitscore.github.client import GitHubClient
from gitscore.jobs import JobRequirementProfile, UnparsedClaim, parse_job_description_with_diagnostics
from gitscore.jobs.types import Necessity
from gitscore.matching import match_job
from gitscore.pipeline.evidence import ExtractionFailure, extract_candidate_evidence
from gitscore.ranking.config import DEFAULT_TOP_N
from gitscore.ranking.job_relevance import JobRelevanceTerm, PREFERRED_WEIGHT, REQUIRED_WEIGHT


def _require_non_blank(value: str, field_name: str) -> None:
    if not value or not value.strip():
        raise ValueError(f"{field_name} must not be empty/whitespace-only")


def _relevance_terms_from_job_profile(job_profile: JobRequirementProfile) -> tuple[JobRelevanceTerm, ...]:
    """Milestone 8D.2 -- bridge `JobRequirementProfile` (`gitscore.jobs`)
    to the neutral `JobRelevanceTerm` retrieval-query representation
    `extract_candidate_evidence()` actually accepts
    (`gitscore.ranking.job_relevance`).

    Lives HERE, not inside `gitscore.jobs` or `gitscore.ranking`,
    precisely because this module is already "the one layer allowed to
    know about all of them together" (see the module docstring above):
    `gitscore.jobs` stays unaware retrieval/ranking exists at all, and
    `gitscore.ranking.job_relevance` stays unaware the job domain model
    exists at all -- see that module's own docstring, "dependency
    direction," and
    `docs/evaluation/MILESTONE_8D2_JOB_AWARE_RETRIEVAL.md` for the full
    rationale.

    A non-technical requirement (`is_technical` False -- no `concept_id`,
    no `alternative_concept_ids`) never produces a term (Part 6 of the
    milestone brief: years-of-experience/degree/communication-skill
    claims must never influence repository retrieval). Necessity maps to
    a fixed weight (`REQUIRED_WEIGHT`/`PREFERRED_WEIGHT`); `Importance`
    is deliberately NOT consulted (see `job_relevance.py`'s own
    docstring for why).
    """
    terms = []
    for requirement in job_profile.requirements:
        if not requirement.is_technical:
            continue
        concept_ids = requirement.alternative_concept_ids or (requirement.concept_id,)
        weight = REQUIRED_WEIGHT if requirement.necessity == Necessity.REQUIRED else PREFERRED_WEIGHT
        terms.append(JobRelevanceTerm(concept_ids=concept_ids, weight=weight))
    return tuple(terms)


@dataclass(frozen=True)
class JobAnalysisResult:
    """Everything one `analyze_job_fit()` call produces, with no stage
    re-run to answer a question a caller might ask of it later.

    `candidate_profile` and `job_profile` are retained as their own
    fields even though `assessment.match_analysis` (Milestone 7A) is
    reachable from `assessment`, because neither is FULLY reachable from
    the match/assessment objects: `JobMatchAnalysis` deliberately keeps
    only the candidate's `coverage` (not the full `evidence`/
    `concept_summaries`), and only the job's `title`/`company` (not the
    full parsed `requirements` tuple or `raw_text`) -- see those two
    classes' own docstrings for why. `JobMatchAnalysis` itself is
    deliberately NOT duplicated as a separate field here: it is reachable
    unchanged via `assessment.match_analysis`.

    `extractor_failures`/`unknown_dependency_names` are
    `extract_candidate_evidence()`'s own per-run diagnostics (Milestone
    5D) -- deliberately kept off `CandidateEvidenceProfile` itself, so
    carried here unchanged rather than dropped or re-derived.

    `unparsed_claims` (Milestone 9C) is the job-side analog: claims
    `segment_description()` judged requirement-shaped for which the
    parser's own per-claim detector chain still produced ZERO
    `JobRequirement` rows -- see `jobs.parsing.parser.UnparsedClaim`'s
    own docstring for why this is a strictly more severe gap than a
    `category="unresolved_requirement"` placeholder (which DOES produce
    a real, inspectable row). A pipeline-level diagnostic, exactly like
    `extractor_failures`/`unknown_dependency_names` above -- never part
    of `job_profile`/`JobRequirementProfile` itself, and never affects
    `assessment.alignment_score` or any matcher/scoring semantics.
    """

    candidate_profile: CandidateEvidenceProfile
    job_profile: JobRequirementProfile
    assessment: JobAssessment
    extractor_failures: tuple[ExtractionFailure, ...] = ()
    unknown_dependency_names: tuple[str, ...] = ()
    unparsed_claims: tuple[UnparsedClaim, ...] = ()


def analyze_job_fit(
    username: str,
    job_description: str,
    *,
    client: GitHubClient | None = None,
    top_n: int = DEFAULT_TOP_N,
    job_title: str | None = None,
    job_company: str | None = None,
) -> JobAnalysisResult:
    """Run the full product pipeline for one candidate against one job
    posting -- GitHub evidence collection, job parsing, matching, and
    assessment -- each exactly once, in that order on the page but job
    parsing first in execution (see below).

    `client` is forwarded UNCHANGED to `extract_candidate_evidence()`,
    which itself only constructs a real `GitHubClient()` when `client`
    is `None` (Milestone 5D's existing default). This function never
    constructs a network client itself, so a caller can inject a fake
    client and `analyze_job_fit()` will never touch the network.

    Execution order is deliberate: `job_description` is parsed FIRST --
    local, deterministic, no network cost -- so a blank or otherwise
    rejected job description fails before any GitHub request is made,
    rather than after already spending part of the candidate's rate-limit
    budget on a request whose result was always going to be discarded.

    Raises `ValueError` for a blank `username` (checked here directly --
    nothing downstream validates it) or a blank `job_description`
    (via `JobRequirementProfile`'s own existing invariant, reused rather
    than re-implemented). Re-raises every GitHub-side exception
    (`GitHubNotFoundError`, `GitHubRateLimitError`, `GitHubRequestError`)
    from `extract_candidate_evidence()` completely unchanged -- this
    function does not catch or wrap them.
    """
    _require_non_blank(username, "username")

    parsed = parse_job_description_with_diagnostics(job_description, title=job_title, company=job_company)
    job_profile = parsed.profile
    relevance_terms = _relevance_terms_from_job_profile(job_profile)

    evidence_result = extract_candidate_evidence(
        username, client=client, top_n=top_n, job_relevance_terms=relevance_terms
    )

    match_analysis = match_job(evidence_result.profile, job_profile)
    assessment = assess_job(match_analysis)

    return JobAnalysisResult(
        candidate_profile=evidence_result.profile,
        job_profile=job_profile,
        assessment=assessment,
        unparsed_claims=parsed.unparsed_claims,
        extractor_failures=evidence_result.extractor_failures,
        unknown_dependency_names=evidence_result.unknown_dependency_names,
    )
