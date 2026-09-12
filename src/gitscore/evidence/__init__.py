"""Milestone 5C -- generalized evidence domain model.

Candidate -> Repository -> Observation -> Technical Concept, with
provenance preserved end to end. See
docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md Parts 6-7 and
docs/ARCHITECTURE.md's Milestone 5C section.

No SQLAlchemy import anywhere in this package -- these are plain,
persistence-independent domain objects (Milestone 5C Part 9: domain
model first, persistence later, not decided here).

Evidence Profile != Job Match. Evidence confidence != candidate
proficiency. Nothing in this package knows what a job description is.
"""
from gitscore.evidence.models import Evidence, RepositoryIdentity
from gitscore.evidence.profile import (
    CandidateEvidenceProfile,
    RepositoryAnalysisCoverage,
    build_candidate_evidence_profile,
)
from gitscore.evidence.summary import (
    CandidateConceptSummary,
    build_concept_summaries,
    evidence_sort_key,
    summarize_concept,
)
from gitscore.evidence.types import EVIDENCE_SCHEMA_VERSION, ConfidenceLevel, EvidenceType

__all__ = [
    "EVIDENCE_SCHEMA_VERSION",
    "CandidateConceptSummary",
    "CandidateEvidenceProfile",
    "ConfidenceLevel",
    "Evidence",
    "EvidenceType",
    "RepositoryAnalysisCoverage",
    "RepositoryIdentity",
    "build_candidate_evidence_profile",
    "build_concept_summaries",
    "evidence_sort_key",
    "summarize_concept",
]
