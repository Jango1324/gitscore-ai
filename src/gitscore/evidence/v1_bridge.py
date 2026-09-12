"""Milestone 5C -- demonstration bridge from existing V1 repo data to Evidence.

Proves compatibility, does NOT migrate V1: this module is not imported
by pipeline/analyze.py, scripts/collect_user.py, scripts/collect_dataset.py,
or any V1 feature extractor. features/ml.py, features/readme.py,
features/languages.py, and scoring/readiness.py are completely
unchanged and continue to run exactly as before. This is only used by
tests/test_v1_evidence_bridge.py to demonstrate that information the V1
pipeline already produces (github/parser.py's parse_repo() output, plus
parse_repo_summary()'s `topics`) CAN be represented under the new
Evidence model without touching any V1 code.

Matching here is deliberately simple (word-boundary substring over the
concept registry's own aliases) -- it is a demonstration, not the
Milestone 5D+ README/dependency evidence extractor.
"""
from __future__ import annotations

import re

from gitscore.concepts.registry import default_registry, resolve_concept
from gitscore.evidence.models import Evidence, RepositoryIdentity
from gitscore.evidence.types import ConfidenceLevel, EvidenceType

_EXTRACTOR_VERSION = "v1-bridge-demo@1"


def evidence_from_repository_language(owner: str, repo: dict) -> list[Evidence]:
    """`repo["primary_language"]` (parse_repo()'s output) -> weak
    REPOSITORY_LANGUAGE evidence.

    Demonstrates the "unresolved concept" path too: a primary language
    not in the small Milestone 5C registry (e.g. "COBOL") still produces
    Evidence, with an "unresolved:..." concept_id -- it is never
    silently dropped.
    """
    language = repo.get("primary_language")
    if not language:
        return []
    resolution = resolve_concept(language)
    return [
        Evidence(
            repository=RepositoryIdentity(owner=owner, name=repo["name"]),
            evidence_type=EvidenceType.REPOSITORY_LANGUAGE,
            raw_observation=f"primary_language={language}",
            concept_id=resolution.concept_id,
            confidence=ConfidenceLevel.WEAK,
            extractor_version=_EXTRACTOR_VERSION,
        )
    ]


def evidence_from_readme_text(owner: str, repo: dict) -> list[Evidence]:
    """Scan parse_repo()'s `readme` text for known concept aliases ->
    moderate README evidence, one Evidence item per matched concept.

    Only demonstrates the RESOLVED path: a README mentioning something
    outside the small Milestone 5C registry produces no evidence here
    (there is no single scalar value to attach an "unresolved" id to
    the way there is for a whole-repo field like primary_language).
    """
    readme = repo.get("readme")
    if not readme:
        return []
    text = readme.lower()
    registry = default_registry()
    matches = []
    for concept in registry.all_concepts():
        for alias in concept.aliases:
            if re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", text):
                matches.append((concept, alias))
                break
    return [
        Evidence(
            repository=RepositoryIdentity(owner=owner, name=repo["name"]),
            evidence_type=EvidenceType.README,
            raw_observation=f"README mentions '{alias}'",
            concept_id=concept.concept_id,
            confidence=ConfidenceLevel.MODERATE,
            extractor_version=_EXTRACTOR_VERSION,
            file_path="README.md",
        )
        for concept, alias in matches
    ]


def evidence_from_topics(owner: str, repo_name: str, topics) -> list[Evidence]:
    """`parse_repo_summary()`'s `topics` list -> weak REPOSITORY_METADATA
    evidence, for topics that resolve to a known concept.

    Unlike the language bridge, unresolved topics are deliberately
    skipped rather than turned into "unresolved:" evidence: GitHub
    topics are frequently non-technical (e.g. "hacktoberfest",
    "portfolio", "awesome-list"), and creating a placeholder observation
    for every such tag would be noise, not evidence of anything. This is
    a detector-design choice (what counts as an "observation worth
    recording"), not a violation of "unknown concepts are never
    silently dropped" -- that rule concerns evidence that WAS extracted,
    not every possible input a detector chooses not to treat as evidence
    at all.
    """
    evidence = []
    for topic in topics or ():
        resolution = resolve_concept(topic)
        if not resolution.matched:
            continue
        evidence.append(
            Evidence(
                repository=RepositoryIdentity(owner=owner, name=repo_name),
                evidence_type=EvidenceType.REPOSITORY_METADATA,
                raw_observation=f"topic={topic}",
                concept_id=resolution.concept_id,
                confidence=ConfidenceLevel.WEAK,
                extractor_version=_EXTRACTOR_VERSION,
            )
        )
    return evidence
