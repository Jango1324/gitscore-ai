"""Milestone 6A -- job requirement domain model.

The structured representation of one technical job posting, designed to
sit opposite `gitscore.evidence.CandidateEvidenceProfile`:

    CandidateEvidenceProfile  +  JobRequirementProfile  -> (future) deterministic matcher

Concept-driven, never role-name-driven -- nothing in this package
branches on a job title or a fixed role enum (see
`docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md` Part 10 and
`docs/ARCHITECTURE.md`'s Milestone 6A section). No parser, no matcher,
no scoring exist yet: every `JobRequirement`/`JobRequirementProfile` in
this milestone is hand-constructed by a caller (tests, for now) --
turning raw job-description text into these objects is future work.

Job Requirement Profile != Match Result. Nothing in this package knows
what a candidate's GitHub evidence looks like.
"""
from gitscore.jobs.models import JobRequirement, SourceSpan
from gitscore.jobs.parsing import JOB_DESCRIPTION_PARSER_VERSION, parse_job_description
from gitscore.jobs.profile import JobRequirementProfile
from gitscore.jobs.types import (
    JOB_REQUIREMENT_SCHEMA_VERSION,
    GithubObservability,
    Importance,
    Necessity,
    ParserConfidence,
)

__all__ = [
    "JOB_DESCRIPTION_PARSER_VERSION",
    "JOB_REQUIREMENT_SCHEMA_VERSION",
    "GithubObservability",
    "Importance",
    "JobRequirement",
    "JobRequirementProfile",
    "Necessity",
    "ParserConfidence",
    "SourceSpan",
    "parse_job_description",
]
