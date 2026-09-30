"""Milestone 7A -- the deterministic requirement matcher.

    CandidateEvidenceProfile  +  JobRequirementProfile
                    |
                    v
            match_job()  ->  JobMatchAnalysis
                    |
        (per requirement) match_requirement()  ->  RequirementMatch

Pure and deterministic with respect to its two input profiles: no
GitHub API calls, no network calls, no LLM, no database reads/writes, no
concept-registry mutation. Same two profiles in -> the same
`JobMatchAnalysis` out, every time.

**`NOT_ASSESSABLE` decision table** -- the one piece of policy this
module owns that is not already spelled out on `MatchStatus` itself:

| `github_observability` | requirement has a concept mapping? | result                     |
|---|---|---|
| `NOT_OBSERVABLE`        | (either)                            | `NOT_ASSESSABLE`           |
| `PARTIALLY_OBSERVABLE`  | no (`concept_id is None` and no `alternative_concept_ids`) | `NOT_ASSESSABLE` |
| `PARTIALLY_OBSERVABLE`  | yes                                 | evaluated like STRONGLY_OBSERVABLE (see below) |
| `STRONGLY_OBSERVABLE`   | no                                  | `NOT_ASSESSABLE`           |
| `STRONGLY_OBSERVABLE`   | yes                                 | evaluated against evidence -> `SUPPORTED` / `NOT_OBSERVED` |

Two things follow from this table that are easy to get wrong by
instinct:

1. `NOT_OBSERVABLE` always wins, even in the (currently unproduced)
   hypothetical of a technical concept mapping attached to a
   `NOT_OBSERVABLE` requirement -- the job-side signal that GitHub
   cannot speak to this AT ALL is never second-guessed by the mere
   presence of a `concept_id`.
2. A `PARTIALLY_OBSERVABLE` requirement that DOES carry a real concept
   mapping is matched EXACTLY like a `STRONGLY_OBSERVABLE` one -- this
   is not "treating PARTIALLY_OBSERVABLE as STRONGLY_OBSERVABLE" by
   accident, it is the deliberate, narrower claim that once there IS a
   concrete concept to check, the evidence-existence mechanism
   (`matching.support.has_sufficient_evidence`) is the single source of
   truth for whether that check succeeds -- `github_observability`
   answers "is there anything concrete to check at all," not "how
   confident must the check be." This is confirmed against real,
   already-existing `JobRequirement` fixtures (Milestone 6A's manual
   examples, `tests/test_job_requirement_manual_examples.py`): "AWS
   experience preferred" and "Comfortable working in Linux
   environments" are both `PARTIALLY_OBSERVABLE` WITH a populated
   `concept_id` -- collapsing every `PARTIALLY_OBSERVABLE` requirement
   into `NOT_ASSESSABLE` regardless of concept mapping would make GitHub
   evidence for AWS/Linux usage (real, checkable dependency/config/
   language evidence) permanently unmatchable, which is not the "smallest
   safe behavior" -- it is strictly LESS truthful than checking it. What
   IS unmatchable today, and correctly `NOT_ASSESSABLE`, is a
   `PARTIALLY_OBSERVABLE` requirement with NO concept mapping at all
   (e.g. `category="leadership"` or the 6B.1 "unsafe" alternative-group
   fallback, `category="alternative_requirement"`) -- there the
   candidate-evidence model has no structured surface to check against
   (no concept id to look up), so inventing support would be pure
   fabrication; `NOT_ASSESSABLE` is the truthful answer there, not a
   discount applied to `SUPPORTED`/`NOT_OBSERVED`.

Necessity, Importance, and ParserConfidence never appear in this
module's logic at all -- Part 12/13 of this milestone's instructions,
directly: whether a requirement is REQUIRED or PREFERRED, HIGH or LOW
importance, or parsed with LOW or HIGH confidence, has zero effect on
whether evidence exists for it. They are read by Milestone 7B off
`RequirementMatch.requirement`, never by this module.
"""
from __future__ import annotations

from gitscore.evidence.profile import CandidateEvidenceProfile
from gitscore.evidence.summary import evidence_sort_key
from gitscore.jobs.models import JobRequirement
from gitscore.jobs.profile import JobRequirementProfile
from gitscore.jobs.types import GithubObservability
from gitscore.matching.models import JobMatchAnalysis, RequirementMatch
from gitscore.matching.support import has_sufficient_evidence
from gitscore.matching.types import MATCHER_VERSION, MatchStatus


def _not_assessable(requirement: JobRequirement) -> RequirementMatch:
    return RequirementMatch(requirement=requirement, status=MatchStatus.NOT_ASSESSABLE)


def match_requirement(
    requirement: JobRequirement,
    candidate_profile: CandidateEvidenceProfile,
) -> RequirementMatch:
    """Match ONE `JobRequirement` against `candidate_profile`'s evidence.

    See this module's docstring for the full `NOT_ASSESSABLE` decision
    table. For a technical requirement that survives that table (single
    `concept_id` or Milestone 6B.1 `alternative_concept_ids`), every
    candidate concept id is checked via
    `matching.support.has_sufficient_evidence`; the requirement is
    `SUPPORTED` if ANY of them has sufficient evidence (OR semantics for
    an alternative group -- Part 6 of this milestone, directly: "Python
    or Go" is satisfied by evidence for EITHER, never requires both),
    with `matched_concept_ids` retaining every alternative that matched,
    not just the first. No fuzzy string matching anywhere here -- the
    parser and concept registry already normalized every concept id on
    both sides (Part 5); this function only ever compares canonical
    concept-id strings.
    """
    if requirement.github_observability == GithubObservability.NOT_OBSERVABLE:
        return _not_assessable(requirement)

    if requirement.is_alternative_group:
        candidate_concept_ids = requirement.alternative_concept_ids
    elif requirement.concept_id is not None:
        candidate_concept_ids = (requirement.concept_id,)
    else:
        # No technical-concept mapping at all -- non-technical claim
        # (Part 6) or the 6B.1 "unsafe" alternative-group fallback
        # (category="alternative_requirement"). Nothing to check.
        return _not_assessable(requirement)

    matched_ids: list[str] = []
    evidence = []
    for concept_id in candidate_concept_ids:
        summary = candidate_profile.concept(concept_id)
        if has_sufficient_evidence(summary):
            matched_ids.append(concept_id)
            evidence.extend(summary.evidence)

    if not matched_ids:
        return RequirementMatch(requirement=requirement, status=MatchStatus.NOT_OBSERVED)

    return RequirementMatch(
        requirement=requirement,
        status=MatchStatus.SUPPORTED,
        matched_concept_ids=tuple(sorted(matched_ids)),
        supporting_evidence=tuple(sorted(evidence, key=evidence_sort_key)),
    )


def match_job(
    candidate_profile: CandidateEvidenceProfile,
    job_profile: JobRequirementProfile,
) -> JobMatchAnalysis:
    """Match every requirement in `job_profile` against
    `candidate_profile`, preserving `job_profile.requirements`' own
    order exactly (that order is meaningful posting order, not an
    arbitrary sequence -- see `JobRequirementProfile`'s own docstring;
    this function never re-sorts it).

    No score, no aggregation beyond `JobMatchAnalysis`'s plain descriptive
    counts -- see that class's docstring for why.
    """
    requirement_matches = tuple(
        match_requirement(requirement, candidate_profile) for requirement in job_profile.requirements
    )
    return JobMatchAnalysis(
        candidate=candidate_profile.candidate,
        job_title=job_profile.title,
        job_company=job_profile.company,
        requirement_matches=requirement_matches,
        coverage=candidate_profile.coverage,
        matcher_version=MATCHER_VERSION,
    )
