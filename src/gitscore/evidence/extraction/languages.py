"""Milestone 5D -- repository-language-statistics evidence.

Converts `GitHubClient.get_repository_languages()`'s raw byte-count
response into Evidence, applying a centralized significance policy so a
repository's 0.01%-of-bytes incidental language (a stray `.sh` helper
script, a vendored asset) does not become "evidence" of anything.
"""
from __future__ import annotations

from gitscore.concepts.registry import resolve_concept
from gitscore.evidence.models import Evidence, RepositoryIdentity
from gitscore.evidence.types import ConfidenceLevel, EvidenceType
from gitscore.github.parser import parse_languages

EXTRACTOR_VERSION = "language:v1"

# Significance policy (Milestone 5D Part 4): a language must account for
# at least this share of the repository's language bytes to be considered
# meaningful at all. Percentage-based (not a raw byte floor) because
# GitHub's language-stats endpoint already normalizes for repository size
# -- a 5% language in a 50MB repo and a 5% language in a 50KB repo are
# equally "a real, non-incidental part of this repository" in a way a
# fixed byte count can't express across repository sizes.
MIN_SIGNIFICANT_PERCENTAGE = 5.0

# A language at or above this share is the repository's dominant
# language (or close to it) -- confident enough to promote from WEAK to
# MODERATE. Below this, the language is present and real but is one of
# several, which is exactly the "declares presence, does not prove
# depth" territory WEAK is meant to describe.
MODERATE_CONFIDENCE_PERCENTAGE = 40.0


def _confidence_for(percentage: float) -> ConfidenceLevel:
    if percentage >= MODERATE_CONFIDENCE_PERCENTAGE:
        return ConfidenceLevel.MODERATE
    return ConfidenceLevel.WEAK


def evidence_from_languages(owner: str, repo_name: str, raw_languages: dict) -> list[Evidence]:
    """`raw_languages` is `GitHubClient.get_repository_languages()`'s raw
    `{language: bytes}` payload (an empty dict for a repository with no
    detectable source, e.g. a docs-only repo -- an expected absence, not
    a failure; callers distinguish an actual fetch failure themselves).

    A meaningful language that GitScore's small registry doesn't know
    (Milestone 5D Part 4's "unknown meaningful languages must follow the
    existing unresolved-concept policy") still produces Evidence, with an
    `unresolved:<language>` concept id -- mirroring `v1_bridge.py`'s
    `primary_language` handling, since a repository's language mix is the
    same kind of well-defined, low-cardinality, always-worth-recording
    field (unlike a free-form dependency list -- see
    `dependency_evidence.py` for why that source is handled differently).
    """
    percentages = parse_languages(raw_languages)
    if not percentages:
        return []

    evidence = []
    for language, percentage in percentages.items():
        if percentage < MIN_SIGNIFICANT_PERCENTAGE:
            continue
        resolution = resolve_concept(language)
        byte_count = raw_languages.get(language, 0)
        evidence.append(
            Evidence(
                repository=RepositoryIdentity(owner=owner, name=repo_name),
                evidence_type=EvidenceType.REPOSITORY_LANGUAGE,
                raw_observation=f"{language}: {percentage:.2f}% ({byte_count} bytes)",
                concept_id=resolution.concept_id,
                confidence=_confidence_for(percentage),
                extractor_version=EXTRACTOR_VERSION,
            )
        )
    return evidence
