"""Milestone 5D -- README concept-mention evidence.

Deterministic, alias-aware, case-insensitive, boundary-aware matching
against the SAME concept registry `resolve_concept()` uses elsewhere --
no separate keyword list, no fuzzy inference, no LLM, no invented
technologies. This is a stricter, registry-driven generalization of
`evidence/v1_bridge.py`'s demonstration README matcher (kept as a
demo-only bridge; this module is the real Milestone 5D extractor).

One Evidence item per matched CONCEPT per repository (never per alias,
never per occurrence) -- a README mentioning "Next.js" three times still
produces exactly one `framework.nextjs` observation, carrying one bounded
snippet from its first occurrence. This is deliberately contextual
mention evidence, not proof of depth of use -- see
`docs/ARCHITECTURE.md`'s confidence-vs-proficiency statement.

Milestone 5D.1 -- matches only `concept.readme_safe_aliases()`, NOT the
full `concept.aliases()` list `resolve_concept()` uses for structured
sources. Free-form prose is a fundamentally more ambiguous matching
context than a package.json key or a GitHub language-stats name: a short
or ordinary-English alias ("go", "next", "js", ...) that's perfectly
unambiguous there produces real false-positive evidence here (see
docs/CHANGELOG_DEV.md's Milestone 5D.1 entry for the real-world
examples this fixed). The exclusion list itself lives on the concept in
`concepts/registry.py` -- this module has no per-alias special-casing.
"""
from __future__ import annotations

import re

from gitscore.concepts.registry import default_registry
from gitscore.evidence.models import Evidence, RepositoryIdentity
from gitscore.evidence.types import ConfidenceLevel, EvidenceType

EXTRACTOR_VERSION = "readme:v2"

# How much surrounding text to keep on each side of a match, so the
# stored observation is a short, inspectable snippet -- never the whole
# README duplicated once per concept.
_SNIPPET_RADIUS = 60

_PATTERN_CACHE: dict[str, "re.Pattern[str]"] = {}


def _alias_pattern(alias: str):
    pattern = _PATTERN_CACHE.get(alias)
    if pattern is None:
        # Same word-boundary approach used throughout the codebase
        # (features/ml.py, ranking/rank.py, evidence/v1_bridge.py): a
        # standalone token, not a substring inside another word --
        # "go" must not match inside "mango", "c" must not match inside
        # "vector". re.IGNORECASE handles case-insensitivity directly
        # against the original (non-lowercased) text, so the extracted
        # snippet preserves the README's real casing.
        pattern = re.compile(
            r"(?<![A-Za-z0-9])" + re.escape(alias) + r"(?![A-Za-z0-9])",
            re.IGNORECASE,
        )
        _PATTERN_CACHE[alias] = pattern
    return pattern


def _bounded_snippet(text: str, start: int, end: int) -> str:
    window_start = max(0, start - _SNIPPET_RADIUS)
    window_end = min(len(text), end + _SNIPPET_RADIUS)
    snippet = text[window_start:window_end]
    return re.sub(r"\s+", " ", snippet).strip()


def evidence_from_readme(
    owner: str, repo_name: str, readme_text: str | None, readme_path: str | None
) -> list[Evidence]:
    """`readme_text`/`readme_path` come from
    `GitHubClient.get_repository_readme_with_path()`. A `None` text (no
    README, or a README the caller could not decode) produces no
    evidence here -- callers are responsible for distinguishing "no
    README" (expected absence) from "README fetch failed" (Milestone 5D
    Part 14) before calling this function.

    Only the RESOLVED path is exercised (mirrors `v1_bridge.py`'s README
    bridge): a mention of something outside the registry produces no
    evidence, since there is no single scalar value (unlike a repo's one
    `primary_language`) to hang an "unresolved" placeholder off of for
    free-form prose -- inventing one would mean guessing at an arbitrary
    substring of the README as "the concept," which the "no arbitrary
    substring matching" rule explicitly forbids.
    """
    if not readme_text:
        return []

    registry = default_registry()
    evidence = []
    for concept in registry.all_concepts():
        match = None
        matched_alias = None
        for alias in concept.readme_safe_aliases():
            found = _alias_pattern(alias).search(readme_text)
            if found is not None:
                match = found
                matched_alias = alias
                break
        if match is None:
            continue
        snippet = _bounded_snippet(readme_text, match.start(), match.end())
        evidence.append(
            Evidence(
                repository=RepositoryIdentity(owner=owner, name=repo_name),
                evidence_type=EvidenceType.README,
                raw_observation=f"README mentions '{matched_alias}': ...{snippet}...",
                concept_id=concept.concept_id,
                confidence=ConfidenceLevel.MODERATE,
                extractor_version=EXTRACTOR_VERSION,
                file_path=readme_path or "README.md",
            )
        )
    return evidence
