"""Milestone 7A -- RequirementMatch and JobMatchAnalysis.

The result of comparing a `CandidateEvidenceProfile`
(gitscore.evidence) against a `JobRequirementProfile` (gitscore.jobs),
one `JobRequirement` at a time. Plain, frozen value objects -- no
SQLAlchemy, no persistence, mirroring every other domain-model package
in this codebase (evidence/models.py, jobs/models.py).

Deliberately contains NO score, NO weighting, NO aggregate verdict, and
NO generated explanation prose -- Milestone 7A establishes matching
SEMANTICS only (see this package's `__init__.py` docstring and
docs/ARCHITECTURE.md's Milestone 7A section). `JobMatchAnalysis` is
built so that Milestone 7B can compute a job-fit score, evidence
coverage percentage, and strengths/gaps prose entirely FROM this object
-- without re-running `match_requirement()` or re-inspecting either
input profile.
"""
from __future__ import annotations

from dataclasses import dataclass

from gitscore.evidence.models import Evidence
from gitscore.evidence.profile import RepositoryAnalysisCoverage
from gitscore.evidence.summary import evidence_sort_key
from gitscore.jobs.models import JobRequirement
from gitscore.matching.types import MatchStatus


@dataclass(frozen=True)
class RequirementMatch:
    """The outcome of matching ONE `JobRequirement` against one
    candidate's evidence.

    `requirement` is retained UNCHANGED (not copied/re-derived) so
    Milestone 7B can read `necessity`/`importance`/`parser_confidence`/
    `github_observability`/`original_text` directly off it -- the
    matcher never needs to duplicate those fields onto this class, and
    7B never needs to re-fetch the original `JobRequirementProfile` to
    recover them.

    `matched_concept_ids` is the subset of the requirement's OWN
    concept id(s) -- `{requirement.concept_id}` for a single-concept
    requirement, or a subset of `requirement.alternative_concept_ids`
    for an alternative group (Milestone 6B.1) -- for which sufficient
    evidence was found. For an alternative group, ALL supported
    alternatives are retained (not just the first), stored SORTED
    (mirroring `JobRequirement.alternative_concept_ids`'s own
    canonical-order convention) so "Python or Go" with both Python and
    Go evidence always produces the identical tuple regardless of
    dict/set iteration order. Always `()` for a non-`SUPPORTED` match.

    `supporting_evidence` is the union of every matched concept's
    `CandidateConceptSummary.evidence`, sorted by the SAME
    `evidence_sort_key` `CandidateEvidenceProfile.evidence` itself uses
    -- deterministic regardless of concept iteration order, and no
    presentation prose generated from it here (Part 14 -- that is a
    Milestone 7B/UI concern). Always `()` for a non-`SUPPORTED` match:
    `NOT_OBSERVED` and `NOT_ASSESSABLE` by definition have no sufficient
    evidence to attach.

    No separate "coverage" field on this class -- `coverage` is a fact
    about the WHOLE candidate evidence profile (how many repositories
    were discovered vs. deeply analyzed), not about any one requirement;
    repeating the identical `RepositoryAnalysisCoverage` object on every
    `RequirementMatch` would be pure duplication with no new information
    per match. It is kept in exactly one place, `JobMatchAnalysis.
    coverage`, mirroring how `CandidateEvidenceProfile` itself keeps
    coverage once rather than duplicating it onto every `Evidence` item.

    No `explanation`/reason-code field: `status` +
    `requirement.github_observability` (why `NOT_ASSESSABLE`) +
    `matched_concept_ids`/`supporting_evidence` (why `SUPPORTED`) are
    jointly sufficient for Milestone 7B to render a sentence like
    "Python is supported by evidence from repositories X and Y" without
    this milestone inventing presentation prose as domain state.
    """

    requirement: JobRequirement
    status: MatchStatus
    matched_concept_ids: tuple[str, ...] = ()
    supporting_evidence: tuple[Evidence, ...] = ()

    def __post_init__(self) -> None:
        if self.status == MatchStatus.SUPPORTED:
            if not self.matched_concept_ids:
                raise ValueError(
                    "RequirementMatch: status=SUPPORTED requires at least one matched_concept_id"
                )
            if not self.supporting_evidence:
                raise ValueError(
                    "RequirementMatch: status=SUPPORTED requires at least one supporting Evidence"
                )
        else:
            if self.matched_concept_ids:
                raise ValueError(
                    f"RequirementMatch: matched_concept_ids must be empty for status={self.status!r}, "
                    f"got {self.matched_concept_ids!r}"
                )
            if self.supporting_evidence:
                raise ValueError(
                    f"RequirementMatch: supporting_evidence must be empty for status={self.status!r}"
                )

        if self.requirement.is_alternative_group:
            allowed_ids = set(self.requirement.alternative_concept_ids)
        elif self.requirement.concept_id is not None:
            allowed_ids = {self.requirement.concept_id}
        else:
            allowed_ids = set()

        extra = set(self.matched_concept_ids) - allowed_ids
        if extra:
            raise ValueError(
                f"RequirementMatch.matched_concept_ids {self.matched_concept_ids!r} contains "
                f"{extra!r}, not part of the requirement's own concept id(s) {allowed_ids!r}"
            )
        if tuple(sorted(self.matched_concept_ids)) != self.matched_concept_ids:
            raise ValueError(
                f"RequirementMatch.matched_concept_ids must be stored sorted, got "
                f"{self.matched_concept_ids!r}"
            )
        if tuple(sorted(self.supporting_evidence, key=evidence_sort_key)) != self.supporting_evidence:
            raise ValueError("RequirementMatch.supporting_evidence must be stored in evidence_sort_key order")

    @property
    def is_supported(self) -> bool:
        return self.status == MatchStatus.SUPPORTED


@dataclass(frozen=True)
class JobMatchAnalysis:
    """The whole-profile result of matching one candidate against one
    job posting: one `RequirementMatch` per `JobRequirement`, in the
    SAME order as `JobRequirementProfile.requirements` (which itself
    preserves posting order, not a re-sort -- see that class's
    docstring) -- never re-sorted here either.

    Deliberately NO 0-100 score, NO weighted aggregation, NO hire/reject
    conclusion, NO strengths/gaps list -- those are Milestone 7B
    concerns that CONSUME this object. The only aggregates here are
    plain, purely descriptive COUNTS by status (`supported_count` etc.)
    -- arithmetic a human could reproduce by counting
    `requirement_matches` by hand, not a weighting decision.

    `coverage` is the candidate's `RepositoryAnalysisCoverage`
    (evidence/profile.py), copied by reference (not recomputed) from the
    `CandidateEvidenceProfile` that was matched -- see
    `RequirementMatch`'s docstring for why it lives here once instead of
    per-requirement. This is what lets Milestone 7B distinguish "Python
    not observed, and every discovered repository was analyzed" from
    "Python not observed, but only 15 of 1,140 repositories were" without
    re-deriving that fact from the candidate profile again.
    """

    candidate: str
    job_title: str | None
    job_company: str | None
    requirement_matches: tuple[RequirementMatch, ...]
    coverage: RepositoryAnalysisCoverage
    matcher_version: str

    def __post_init__(self) -> None:
        if not self.candidate.strip():
            raise ValueError("JobMatchAnalysis.candidate must not be empty/whitespace-only")
        if not self.matcher_version.strip():
            raise ValueError("JobMatchAnalysis.matcher_version must not be empty/whitespace-only")

    @property
    def requirement_count(self) -> int:
        return len(self.requirement_matches)

    def matches_with_status(self, status: MatchStatus) -> tuple[RequirementMatch, ...]:
        return tuple(match for match in self.requirement_matches if match.status == status)

    @property
    def supported_count(self) -> int:
        return len(self.matches_with_status(MatchStatus.SUPPORTED))

    @property
    def not_observed_count(self) -> int:
        return len(self.matches_with_status(MatchStatus.NOT_OBSERVED))

    @property
    def not_assessable_count(self) -> int:
        return len(self.matches_with_status(MatchStatus.NOT_ASSESSABLE))
