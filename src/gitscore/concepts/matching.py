"""Milestone 6B -- shared boundary-aware alias matching.

Extracted from `evidence/extraction/readme.py` (Milestone 5D) so that
BOTH README extraction and job-description parsing (Milestone 6B,
`jobs/parsing/concepts.py`) use the exact same word-boundary matching
mechanics against free-form prose, instead of two independent regex
implementations that could silently drift apart. This module contains
ONLY the pattern-building primitive -- it has no opinion about which
aliases are safe to scan (that's `TechnicalConcept.readme_safe_aliases()`,
concepts/models.py) or what to do with a match (that's each caller's own
concern).
"""
from __future__ import annotations

import re

_PATTERN_CACHE: dict[str, "re.Pattern[str]"] = {}


def alias_pattern(alias: str) -> "re.Pattern[str]":
    """A standalone-token, case-insensitive pattern for `alias`.

    A word-boundary match, not a substring match: "go" must not match
    inside "mango", "c" must not match inside "vector". Case-insensitive
    via `re.IGNORECASE` against the ORIGINAL (non-lowercased) text, so a
    caller extracting a snippet around a match preserves the source's
    real casing.
    """
    pattern = _PATTERN_CACHE.get(alias)
    if pattern is None:
        pattern = re.compile(
            r"(?<![A-Za-z0-9])" + re.escape(alias) + r"(?![A-Za-z0-9])",
            re.IGNORECASE,
        )
        _PATTERN_CACHE[alias] = pattern
    return pattern
