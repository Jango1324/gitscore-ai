"""Milestone 6B Part 8 -- importance inference.

Deliberately simple and explainable -- NOT a claim of precise business
priority. Default `MEDIUM`; a small set of explicit strong-emphasis
words upgrades to `HIGH`; a small set of explicit hedge words downgrades
to `LOW`; a `PREFERRED` requirement with no strong-emphasis override
defaults to `LOW` (a "plus" is inherently secondary to a stated
requirement). No floating-point weights -- ordinal only, matching
`Importance`'s own "no fake precision" design (Milestone 6A Part 3).
"""
from __future__ import annotations

import re

from gitscore.jobs.types import Importance, Necessity

_HIGH_MARKER = re.compile(
    r"\bcritical\b|\bessential\b|\bexpert\b|\bdeep experience\b|\bextensive experience\b|"
    r"\bstrong proficiency\b|\bhighly proficient\b",
    re.IGNORECASE,
)
_LOW_MARKER = re.compile(
    r"\bfamiliarity with\b|\bexposure to\b|\bbasic knowledge of\b|\bbasic understanding of\b|"
    r"\bsome experience\b",
    re.IGNORECASE,
)


def infer_importance(claim_text: str, necessity: Necessity) -> Importance:
    if _HIGH_MARKER.search(claim_text):
        return Importance.HIGH
    if _LOW_MARKER.search(claim_text):
        return Importance.LOW
    if necessity == Necessity.PREFERRED:
        return Importance.LOW
    return Importance.MEDIUM
