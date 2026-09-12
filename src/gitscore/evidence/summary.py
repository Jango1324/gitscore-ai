"""Milestone 5C -- CandidateConceptSummary: Evidence aggregated per concept.

Evidence is the source of truth (architectural rules 1-2): a
CandidateConceptSummary is always DERIVED by summarize_concept() /
build_concept_summaries() from a pool of Evidence, never independently
constructed or mutated by other code. There is exactly one place
evidence "lives" -- this module never becomes a second, independently
writable store of the same facts.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from gitscore.evidence.models import Evidence, RepositoryIdentity
from gitscore.evidence.types import ConfidenceLevel


def evidence_sort_key(evidence: Evidence):
    """Deterministic order for a collection of Evidence, regardless of
    extraction/collection order: repository, then file, then evidence
    type, then the raw observation text itself.
    """
    return (
        evidence.repository.owner,
        evidence.repository.name,
        evidence.file_path or "",
        evidence.evidence_type.value,
        evidence.raw_observation,
    )


@dataclass(frozen=True)
class CandidateConceptSummary:
    """Evidence for one concept, aggregated deterministically.

    Not intended to be constructed directly by callers outside this
    module -- use summarize_concept() / build_concept_summaries(), which
    apply the duplicate policy and canonical ordering documented there.
    """

    concept_id: str
    evidence: tuple[Evidence, ...]

    @property
    def evidence_count(self) -> int:
        return len(self.evidence)

    @property
    def repositories(self) -> tuple[RepositoryIdentity, ...]:
        """Distinct repositories supporting this concept, sorted deterministically."""
        seen: list[RepositoryIdentity] = []
        for item in self.evidence:
            if item.repository not in seen:
                seen.append(item.repository)
        seen.sort(key=lambda repo: (repo.owner, repo.name))
        return tuple(seen)

    @property
    def strongest_confidence(self) -> ConfidenceLevel:
        return max(item.confidence for item in self.evidence)


def summarize_concept(concept_id: str, evidence_items) -> CandidateConceptSummary | None:
    """Build the summary for one concept from a pool of Evidence.

    Filters `evidence_items` to those matching `concept_id`.

    Duplicate policy: EXACT structural duplicates (identical repository,
    file_path, evidence_type, concept_id, raw_observation, confidence,
    extractor_version, location, collected_at) collapse to a single
    entry -- e.g. if the same detector runs twice and produces the
    identical Evidence, it must not double-count in `evidence_count`.
    Two Evidence items that merely support the same concept but differ
    in ANY field (different repo, different file, different raw text,
    even a different confidence from a different extractor version) are
    NOT duplicates and are both kept.

    Returns None if no evidence supports this concept -- there is no
    such thing as an empty CandidateConceptSummary; absence of evidence
    means the concept's key is simply absent from a profile, not a
    zero-evidence summary object floating around.
    """
    relevant = {item for item in evidence_items if item.concept_id == concept_id}
    if not relevant:
        return None
    ordered = tuple(sorted(relevant, key=evidence_sort_key))
    return CandidateConceptSummary(concept_id=concept_id, evidence=ordered)


def build_concept_summaries(evidence_items):
    """Group a full Evidence pool into one CandidateConceptSummary per
    concept_id present. Deterministic regardless of input order.

    Returns a plain dict {concept_id: CandidateConceptSummary}. Concepts
    with zero supporting evidence never appear as a key.
    """
    by_concept: dict[str, list[Evidence]] = defaultdict(list)
    for item in evidence_items:
        by_concept[item.concept_id].append(item)

    summaries: dict[str, CandidateConceptSummary] = {}
    for concept_id, items in by_concept.items():
        summary = summarize_concept(concept_id, items)
        if summary is not None:
            summaries[concept_id] = summary
    return summaries
