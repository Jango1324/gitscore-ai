"""Milestone 6A -- JobRequirementProfile: one job posting, structured.

The job-side counterpart to evidence/profile.py's
CandidateEvidenceProfile -- the future architecture is:

    CandidateEvidenceProfile  +  JobRequirementProfile  -> (future) deterministic matcher

Candidate-independent by construction (see the dataclass docstring and
its pinned test, `tests/test_job_requirement_profile.py::
test_profile_has_no_candidate_or_match_fields`, mirroring
CandidateEvidenceProfile's own `test_profile_has_no_job_related_fields`).
"""
from __future__ import annotations

from dataclasses import dataclass

from gitscore.jobs.models import JobRequirement
from gitscore.jobs.types import JOB_REQUIREMENT_SCHEMA_VERSION, Necessity


@dataclass(frozen=True)
class JobRequirementProfile:
    """One actual job posting's structured requirements.

    Unlike `CandidateEvidenceProfile.evidence` (deduplicated SILENTLY --
    see evidence/summary.py's duplicate policy, built for a corroboration
    model where the same fact observed twice is still just one fact),
    `requirements` here REJECTS exact structural duplicates instead
    (`__post_init__` raises `ValueError`). The two models solve different
    problems: repeated identical Evidence is expected and harmless
    (multiple detectors legitimately re-observe the same real fact);
    an exact duplicate JobRequirement -- same text, same span, same
    everything -- has no legitimate source (a job posting's requirements
    are each supposed to be one distinct claim) and is far more likely a
    construction bug than genuine data, which Milestone 6A Part 11 asks
    domain objects to reject rather than silently absorb.

    `requirements` preserves EXACTLY the order given, unlike
    `CandidateEvidenceProfile.evidence` (which is canonically re-sorted
    by `evidence_sort_key` regardless of input order). This is also a
    deliberate difference, not an oversight: an Evidence pool has no
    inherent meaningful order, so a canonical sort makes equal inputs
    produce an identical, comparison-friendly tuple. A job posting's
    requirements DO have a meaningful order -- the sequence they appear
    in the posting, often itself informative (earlier = more prominent)
    -- so "deterministic ordering" here means "the same input order
    always produces the same output tuple," never a re-sort that would
    destroy that information.

    No job-independent-profile-style derived/aggregate field exists here
    (contrast `CandidateEvidenceProfile.concept_summaries`, always
    DERIVED from its `evidence`) -- there is nothing to aggregate yet;
    that is future matcher work. Consequently this class needs no
    separate "only intended constructor" builder function the way
    `build_candidate_evidence_profile()` exists for its sibling --
    `__post_init__` alone is sufficient to protect its invariants.

    Deliberately contains NO candidate-side field of any kind: no
    candidate/username, no Evidence, no match score, no coverage score,
    no strengths/gaps, no repository references, no alternative roles.
    Those are downstream, future-matcher concerns that CONSUME this
    profile plus a CandidateEvidenceProfile -- they do not live inside
    either one.
    """

    raw_text: str
    requirements: tuple[JobRequirement, ...]
    parser_version: str
    title: str | None = None
    company: str | None = None
    schema_version: int = JOB_REQUIREMENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.raw_text.strip():
            raise ValueError("JobRequirementProfile.raw_text must not be empty/whitespace-only")
        if not self.parser_version.strip():
            raise ValueError("JobRequirementProfile.parser_version must not be empty")

        text_length = len(self.raw_text)
        for requirement in self.requirements:
            span = requirement.source_span
            if span is not None and span.end > text_length:
                raise ValueError(
                    f"JobRequirement source_span {span!r} falls outside raw_text "
                    f"bounds (length {text_length}): {requirement.original_text!r}"
                )

        if len(set(self.requirements)) != len(self.requirements):
            raise ValueError(
                "JobRequirementProfile.requirements contains an exact structural "
                "duplicate -- two JobRequirement entries with identical fields; "
                "see the class docstring for why this is rejected, not deduplicated"
            )

    @property
    def requirement_count(self) -> int:
        return len(self.requirements)

    def required_requirements(self) -> tuple[JobRequirement, ...]:
        return tuple(r for r in self.requirements if r.necessity == Necessity.REQUIRED)

    def preferred_requirements(self) -> tuple[JobRequirement, ...]:
        return tuple(r for r in self.requirements if r.necessity == Necessity.PREFERRED)
