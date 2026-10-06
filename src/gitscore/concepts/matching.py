"""Milestone 6B -- shared boundary-aware alias matching.

Extracted from `evidence/extraction/readme.py` (Milestone 5D) so that
BOTH README extraction and job-description parsing (Milestone 6B,
`jobs/parsing/concepts.py`) use the exact same word-boundary matching
mechanics against free-form prose, instead of two independent regex
implementations that could silently drift apart. This module contains
ONLY the pattern-building primitive and (Milestone 8D.1)
`select_longest_overlapping_matches()`, the shared "most-specific alias
wins" conflict resolution both callers now apply -- it has no opinion
about which aliases are safe to scan (that's
`TechnicalConcept.readme_safe_aliases()`, concepts/models.py) or what to
do with a match beyond resolving overlaps (that's each caller's own
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


def select_longest_overlapping_matches(spans):
    """Milestone 8D.1 -- "most-specific alias wins" for overlapping
    concept matches found in the SAME piece of free-form text.

    `spans` is an iterable of `(start, end, payload)`. Word-boundary
    matching (`alias_pattern`, above) is run independently PER ALIAS, so
    two different concepts whose aliases textually overlap at the same
    position both produce a candidate match -- the real-world example
    that motivated this function (Milestone 8C's evaluation, Section 6):
    "React Native" satisfies BOTH `framework.react`'s bare "react" alias
    (a true word-boundary match: "react" is immediately followed by a
    space) AND `framework.react_native`'s "react native" alias, and
    without this filter the shorter, less specific "react" match would
    silently stand in for the real technology actually named.

    This is the generic, data-driven resolution: among mutually
    overlapping candidate spans, keep only the ones NOT fully shadowed by
    a STRICTLY LONGER overlapping span (the longer alias is, by
    construction, the more specific/informative match) -- no per-concept
    special-casing, so it generalizes to any future overlapping alias
    pair (e.g. a hypothetical "Next" vs "Next.js" collision not already
    handled by `readme_unsafe_aliases`), not just this one. Equal-length
    overlapping spans are NOT considered shadowed by each other -- both
    survive (there is no principled way to prefer one over the other from
    length alone), which cannot happen for any pair of DISTINCT aliases in
    the current registry but is the deliberately conservative choice if
    it ever does. Returns the surviving `payload`s ordered by
    `(start, end)`, deterministic for a fixed input.
    """
    items = [(start, end, payload) for start, end, payload in spans]
    length = lambda item: item[1] - item[0]  # noqa: E731
    by_length_desc = sorted(range(len(items)), key=lambda i: (-length(items[i]), i))

    kept: list[tuple[int, int, object]] = []
    for index in by_length_desc:
        start, end, payload = items[index]
        shadowed = any(
            start < k_end and end > k_start and (k_end - k_start) > (end - start)
            for k_start, k_end, _ in kept
        )
        if not shadowed:
            kept.append((start, end, payload))

    kept.sort(key=lambda item: (item[0], item[1]))
    return [payload for _, _, payload in kept]
