"""Milestone 11-G2 Phase 3 -- three candidate strategies for section-
aware necessity resolution, compared BEFORE any production code is
touched. Each takes the same (text, section_kind, document_has_recognized_heading)
triple and returns the necessity string it would assign ("REQUIRED" /
"PREFERRED" / None), evaluation-only, never imported by production.

Option A -- reuse of existing deterministic section-state classification:
    calls the REAL, unmodified `jobs.parsing.necessity.resolve_necessity_hint`
    and `jobs.parsing.segmentation._SectionKind`/`_SECTION_NECESSITY_HINT`
    directly. Zero new classification logic.

Option B -- dedicated, INDEPENDENT offline structural context propagation:
    a parallel, hand-rolled section-necessity mapping authored fresh for
    this comparison, deliberately NOT importing segmentation.py's own
    constants -- demonstrates the duplication/drift risk of building a
    second, independently-evolving classifier instead of reusing the
    first.

Option C -- hybrid (section intent + local language cues + conservative
    conflict handling): literally Option A's own three-step design
    (local marker always wins -> section-origin eligibility -> narrative
    veto) is ALREADY a hybrid of exactly these three things. Implemented
    here as a thin wrapper around Option A, to make that convergence an
    explicit, measured finding rather than an assumption.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gitscore.jobs.parsing.narrative import contains_narrative_cue  # noqa: E402
from gitscore.jobs.parsing.necessity import _has_local_marker, resolve_necessity_hint  # noqa: E402
from gitscore.jobs.types import Necessity  # noqa: E402


def option_a(text: str, section_kind: str | None, document_has_recognized_heading: bool) -> str | None:
    """Reuse: the REAL `resolve_necessity_hint`, fed a default hint
    derived from the REAL `_SectionKind`/`_SECTION_NECESSITY_HINT`
    (segmentation.py), mirroring exactly how `Claim.necessity_hint` is
    already computed there."""
    from gitscore.jobs.parsing.segmentation import _SectionKind, _SECTION_NECESSITY_HINT

    if section_kind is None:
        default_hint = Necessity.REQUIRED  # Milestone 6B's own "no section at all" default
    else:
        kind = _SectionKind[section_kind]
        default_hint = None if kind in (_SectionKind.UNKNOWN, _SectionKind.LEARNING) else (
            _SECTION_NECESSITY_HINT.get(kind, Necessity.REQUIRED)
        )
    hint = resolve_necessity_hint(
        text, default_hint, section_kind=section_kind, document_has_recognized_heading=document_has_recognized_heading,
    )
    from gitscore.jobs.parsing.necessity import infer_necessity

    necessity = infer_necessity(text, hint)
    return necessity.value.upper() if necessity is not None else None


def option_b(text: str, section_kind: str | None, document_has_recognized_heading: bool) -> str | None:
    """Independent, hand-rolled duplicate -- deliberately NOT importing
    segmentation.py's own `_SectionKind`/`_SECTION_NECESSITY_HINT`. An
    independently-authored mapping for comparison purposes only."""
    import re

    required_marker = re.compile(r"\brequired\b|\bmust\s+have\b|\bmust\s+be\b|\bmandatory\b", re.IGNORECASE)
    preferred_marker = re.compile(r"\bpreferred\b|\bnice[-\s]to[-\s]have\b|\ba\s+plus\b|\bbonus\b", re.IGNORECASE)

    if required_marker.search(text):
        return "REQUIRED"
    if preferred_marker.search(text):
        return "PREFERRED"

    # Independently-authored section mapping (a plausible but SEPARATE
    # design decision from segmentation.py's own table -- e.g. this
    # version omits "RESPONSIBILITY" from the always-REQUIRED-hint set
    # since it conflates duty wording with qualification wording,
    # which is a DIFFERENT judgment call than segmentation.py already
    # made for its own, differently-scoped purpose).
    always_eligible = {"REQUIRED", "PREFERRED"}
    if section_kind in always_eligible:
        if contains_narrative_cue(text):
            return None
        return section_kind
    if section_kind is None and not document_has_recognized_heading:
        if contains_narrative_cue(text):
            return None
        return "REQUIRED"
    return None


def option_c(text: str, section_kind: str | None, document_has_recognized_heading: bool) -> str | None:
    """Hybrid: section intent + local language cues + conservative
    conflict handling. Implemented as Option A -- see module docstring
    for why this convergence is a measured finding, not an assumption."""
    return option_a(text, section_kind, document_has_recognized_heading)


STRATEGIES = {"option_a": option_a, "option_b": option_b, "option_c": option_c}
