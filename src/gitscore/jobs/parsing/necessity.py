"""Milestone 6B Part 7 -- necessity inference.

Deterministic precedence: LOCAL wording in the claim's own text always
wins over the section-derived default (`Claim.necessity_hint`, from
`segmentation.py`) -- "Preferred Qualifications: ... Kubernetes is
required" (an unusual but possible real-world contradiction) resolves to
REQUIRED, matching what the sentence itself actually says. If a claim's
text contains BOTH a REQUIRED and a PREFERRED local marker (rare,
genuinely ambiguous phrasing), REQUIRED wins -- the conservative
direction: never under-state what the posting demands.

Milestone 10B: `necessity_hint` (and this function's return value)
widens to `Necessity | None` -- `None` represents
`_SectionKind.UNKNOWN` (segmentation.py), a claim admitted from text
following an unrecognized heading with no section-derived default to
fall back on. The precedence rule above is UNCHANGED: a local marker in
the claim's own text still wins first, regardless of the hint: even a
claim with `necessity_hint=None` resolves to a real `Necessity` if its
own text says "required" or "a plus." Only when NEITHER a local marker
fires NOR a real hint exists does this function return `None`, telling
`jobs/parsing/parser.py::_requirements_from_claim` to produce no scored
`JobRequirement` for it at all.
"""
from __future__ import annotations

import re

from gitscore.jobs.types import Necessity

_REQUIRED_MARKER = re.compile(
    r"\brequired\b|\bmust have\b|\bmust be\b|\bmandatory\b|\bessential\b|\bneed to have\b",
    re.IGNORECASE,
)
_PREFERRED_MARKER = re.compile(
    r"\bpreferred\b|\bnice[- ]to[- ]have\b|\bnice to haves?\b|\ba plus\b|\bbonus\b|"
    r"\bideally\b|\bwould be nice\b",
    re.IGNORECASE,
)


def infer_necessity(claim_text: str, necessity_hint: Necessity | None) -> Necessity | None:
    if _REQUIRED_MARKER.search(claim_text):
        return Necessity.REQUIRED
    if _PREFERRED_MARKER.search(claim_text):
        return Necessity.PREFERRED
    return necessity_hint
