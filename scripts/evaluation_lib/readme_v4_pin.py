"""Milestone 11-G22-S1 -- explicit `readme:v4` pin for HISTORICAL research reproduction (not production).

Production became `readme:v5` in G22-S1. v5 differs from v4 in exactly one place: `readme_context`'s heading index
(v4: ATX headings only; v5: ATX + setext headings, see `readme_context._heading_spans`). Everything else -- alias
table, 8D.3 denylist and adjacency cues, fall-through, overlap resolution, deduplication, MODERATE confidence -- is
byte-for-byte the same code.

The G22-R, G22-R2, G22-R3, G22-R4 and G22-R5 research measured `readme:v4`; their committed reports, tests and
runners describe that configuration. `pinned()` restores exactly `readme:v4` for the duration of a `with` block:

  * the README extractor (and any research code calling `readme_context.build_context`) gets a ReadmeContext built
    from production's own, unchanged ATX-only helper `_atx_heading_spans` -- the literal v4 heading index;
  * evidence is labelled `readme:v4` (`readme.EXTRACTOR_VERSION`, read at call time by `evidence_from_readme`).

Nothing in `src/` imports this module. Outside a `with pinned()` block production behaves as `readme:v5`.
"""
from __future__ import annotations

import contextlib

from gitscore.evidence.extraction import readme as readme_mod
from gitscore.evidence.extraction import readme_context as rc

V4 = "readme:v4"
EXTRACTOR_VERSION = V4  # what the historical research measured
# production versions this pin knows how to map back to v4 exactly
_REPRODUCIBLE_FROM = ("readme:v4", "readme:v5")
PRODUCTION_VERSION_AT_IMPORT = readme_mod.EXTRACTOR_VERSION


class ReadmeV4Context(rc.ReadmeContext):
    """The readme:v4 heading index: ATX headings only (production's unchanged `_atx_heading_spans`)."""

    def __init__(self, text: str) -> None:  # noqa: D401 -- deliberately not calling the v5 initialiser
        self._headings = rc._atx_heading_spans(text)


def reproduces_v4() -> bool:
    """True when the current production README extractor can be pinned back to readme:v4 exactly."""
    return readme_mod.EXTRACTOR_VERSION in _REPRODUCIBLE_FROM


@contextlib.contextmanager
def pinned():
    current = readme_mod.EXTRACTOR_VERSION
    if current == V4:  # already v4 (inside another pin, or a pre-G22-S1 checkout): nothing to do
        yield
        return
    if current not in _REPRODUCIBLE_FROM:
        raise RuntimeError(f"readme_v4_pin cannot reproduce readme:v4 from {current!r}; extend it explicitly")
    saved = (readme_mod.EXTRACTOR_VERSION, readme_mod.build_context, rc.build_context)
    readme_mod.EXTRACTOR_VERSION = V4
    readme_mod.build_context = ReadmeV4Context
    rc.build_context = ReadmeV4Context
    try:
        yield
    finally:
        readme_mod.EXTRACTOR_VERSION, readme_mod.build_context, rc.build_context = saved
