"""Milestone 5C -- RepositoryIdentity and Evidence.

Plain, persistence-independent domain objects (dataclasses, no
SQLAlchemy import anywhere in this package) -- see
docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md Part 7 (Evidence
Provenance Model). Persistence is an explicit later decision (Milestone
5C Part 9); nothing here assumes or depends on how these objects are
eventually stored, if at all.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from gitscore.concepts.registry import is_unresolved_concept_id
from gitscore.evidence.types import ConfidenceLevel, EvidenceType


@dataclass(frozen=True)
class RepositoryIdentity:
    """A minimal, stable reference to one candidate's repository.

    Deliberately identity-only -- not a full repository summary. A
    richer, ranking-purposed view already exists
    (gitscore.ranking.RepositoryRankingResult, Milestone 5B) and is
    intentionally not duplicated here: Evidence only needs to say WHICH
    repository, never how that repository ranked or scored.
    """

    owner: str
    name: str


@dataclass(frozen=True)
class Evidence:
    """One provenance-backed observation supporting a technical concept.

    Frozen and fully hashable (every field is itself hashable), so a
    collection of Evidence can be deduplicated with a plain `set()` --
    see evidence/summary.py for the exact duplicate policy this enables.

    `concept_id` is always populated: either a real TechnicalConcept's
    id, or a deterministic "unresolved:<term>" id from
    concepts.registry.resolve_concept() /
    concepts.registry.unresolved_concept_id() (Milestone 5C Part 3
    policy -- an unmatched observation is never silently dropped).

    No `evidence_id` field: at this stage Evidence is a pure value
    object, compared and deduplicated structurally. A synthetic
    identifier is a natural persistence-layer concern (Milestone 5C
    Part 9 defers persistence entirely) and would be premature here.

    No `source_url`: derivable on demand from `repository` + `file_path`
    by a caller that also knows the hosting convention; storing it
    redundantly here risked getting out of sync with repository/
    file_path for no benefit at this stage.
    """

    repository: RepositoryIdentity
    evidence_type: EvidenceType
    raw_observation: str
    concept_id: str
    confidence: ConfidenceLevel
    extractor_version: str
    file_path: str | None = None
    location: str | None = None
    collected_at: datetime | None = None

    @property
    def is_resolved(self) -> bool:
        """False if `concept_id` is an "unresolved:..." placeholder."""
        return not is_unresolved_concept_id(self.concept_id)
