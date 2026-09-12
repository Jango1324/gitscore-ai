"""Milestone 5C -- deterministic term normalization.

Pure string normalization, no registry dependency (kept separate from
registry.py specifically to avoid a circular import: registry.py uses
`normalize_term` to normalize aliases at construction time; the
resolution logic that needs both the registry AND this function lives
in registry.py itself, not here).

Deliberately narrow: only case and a small, curated set of punctuation
are normalized. This is NOT a general slugifier -- stripping every
non-alphanumeric character would silently collide unrelated concepts
(e.g. "C++" and "C" must never normalize to the same string).
"""
from __future__ import annotations

import re

_PUNCTUATION_TO_STRIP = re.compile(r"[.,]")
_WHITESPACE_RUN = re.compile(r"\s+")


def normalize_term(term: str) -> str:
    """Lowercase, strip periods/commas, collapse whitespace.

    Examples: "PostgreSQL" -> "postgresql", "React.js" -> "reactjs",
    "Amazon Web Services" -> "amazon web services".
    """
    cleaned = _PUNCTUATION_TO_STRIP.sub("", term.strip().lower())
    return _WHITESPACE_RUN.sub(" ", cleaned)
