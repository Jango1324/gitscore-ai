"""Milestone 11-G22-S2 -- explicit `readme:v5` pin for HISTORICAL reproduction of G22-S1 (not production).

Production became `readme:v6` in G22-S2. v6 differs from v5 in exactly one place: `readme.evidence_from_readme`
skips an occurrence that `readme._inside_longer_other_concept_match` reports as lying inside a strictly longer match
of another concept, and keeps scanning (v5 selected it and then lost the concept in overlap resolution). Everything
else -- the v5 setext-aware heading index, 8D.3 exclusions, alias order, fall-through, the final 8D.1 overlap pass,
deduplication, snippets -- is the same code.

`pinned()` restores exactly `readme:v5` for the duration of a `with` block: the v6 predicate is replaced by one that
never skips (the literal v5 selection) and evidence is labelled `readme:v5`. Restored on normal exit and on
exceptions. Nested use is safe: inside an active pin (or on genuine v5 code) it is a no-op. Nothing in `src/` imports
this module.
"""
from __future__ import annotations

import contextlib

from gitscore.evidence.extraction import readme as readme_mod

V5 = "readme:v5"
EXTRACTOR_VERSION = V5  # what G22-S1 measured
_REPRODUCIBLE_FROM = ("readme:v5", "readme:v6")


def _v5_never_skips(start: int, end: int, concept_id: str, all_occurrences) -> bool:
    return False


def reproduces_v5() -> bool:
    return readme_mod.EXTRACTOR_VERSION in _REPRODUCIBLE_FROM


@contextlib.contextmanager
def pinned():
    current = readme_mod.EXTRACTOR_VERSION
    if current == V5:  # genuine v5 code, or already pinned
        yield
        return
    if current != "readme:v6":
        raise RuntimeError(f"readme_v5_pin cannot reproduce readme:v5 from {current!r}; extend it explicitly")
    saved = (readme_mod.EXTRACTOR_VERSION, readme_mod._inside_longer_other_concept_match)
    readme_mod.EXTRACTOR_VERSION = V5
    readme_mod._inside_longer_other_concept_match = _v5_never_skips
    try:
        yield
    finally:
        readme_mod.EXTRACTOR_VERSION, readme_mod._inside_longer_other_concept_match = saved
