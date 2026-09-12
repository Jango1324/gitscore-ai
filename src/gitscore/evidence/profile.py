"""Milestone 5C -- CandidateEvidenceProfile: the job-independent whole.

Contains WHAT evidence exists for a candidate and WHICH repositories
were looked at -- nothing about any job, required/preferred skills, a
match score, or alternative roles. Those are explicitly out of scope
here and remain Milestone 6A+/7A+ concerns -- see
docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from gitscore.concepts.registry import CONCEPT_REGISTRY_VERSION
from gitscore.evidence.models import Evidence, RepositoryIdentity
from gitscore.evidence.summary import (
    CandidateConceptSummary,
    build_concept_summaries,
    evidence_sort_key,
)
from gitscore.evidence.types import EVIDENCE_SCHEMA_VERSION


@dataclass(frozen=True)
class RepositoryAnalysisCoverage:
    """Which repositories GitScore knew about vs. actually looked at.

    Exists specifically to support future INSUFFICIENT_ANALYSIS
    semantics (docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md Part 16)
    combined with Milestone 5B's top-N repository ranking:
    "GitScore discovered 1,140 repositories but deeply analyzed 15" must
    be a representable, queryable fact on the profile itself, not
    something an explanation layer has to reconstruct after the fact.

    Milestone 5C does not populate `analyzed` from a real deep-analysis
    step (no such extractor exists yet) -- callers pass whatever they
    have (e.g. an empty tuple, or Milestone 5B's ranked top-N).
    """

    discovered: tuple[RepositoryIdentity, ...]
    analyzed: tuple[RepositoryIdentity, ...]

    @property
    def discovered_count(self) -> int:
        return len(self.discovered)

    @property
    def analyzed_count(self) -> int:
        return len(self.analyzed)

    @property
    def is_complete(self) -> bool:
        """True if every discovered repository was deeply analyzed."""
        return self.analyzed_count == self.discovered_count


@dataclass(frozen=True)
class CandidateEvidenceProfile:
    """The full, job-independent evidence picture for one candidate.

    `evidence` is the source of truth; `concept_summaries` is always
    DERIVED from it by build_candidate_evidence_profile() (the only
    intended constructor) and exposed as a read-only mapping
    (`types.MappingProxyType`) so nothing downstream can quietly diverge
    from the evidence it was built from.

    Deliberately contains no job-related field of any kind -- no target
    job, no match score, no required/preferred skills, no alternative
    roles. Job-conditional results are a separate object, computed
    later, from this profile plus a job requirement profile.
    """

    candidate: str
    coverage: RepositoryAnalysisCoverage
    evidence: tuple[Evidence, ...]
    concept_summaries: "MappingProxyType[str, CandidateConceptSummary]"
    evidence_schema_version: int
    concept_registry_version: int
    collected_at: datetime | None = None

    def concept(self, concept_id: str) -> CandidateConceptSummary | None:
        return self.concept_summaries.get(concept_id)


def build_candidate_evidence_profile(
    candidate: str,
    discovered,
    analyzed,
    evidence_items,
    *,
    collected_at: datetime | None = None,
) -> CandidateEvidenceProfile:
    """The only intended way to construct a CandidateEvidenceProfile.

    Deduplicates `evidence_items` (see evidence/summary.py's duplicate
    policy), derives `concept_summaries` from the deduplicated set, and
    stamps the current schema/registry versions.
    """
    deduplicated = tuple(sorted(set(evidence_items), key=evidence_sort_key))
    summaries = build_concept_summaries(deduplicated)

    return CandidateEvidenceProfile(
        candidate=candidate,
        coverage=RepositoryAnalysisCoverage(
            discovered=tuple(discovered), analyzed=tuple(analyzed)
        ),
        evidence=deduplicated,
        concept_summaries=MappingProxyType(summaries),
        evidence_schema_version=EVIDENCE_SCHEMA_VERSION,
        concept_registry_version=CONCEPT_REGISTRY_VERSION,
        collected_at=collected_at,
    )
