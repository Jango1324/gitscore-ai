"""Milestone 6B Part 12 -- parser confidence assignment.

Represents confidence in the PARSE/INTERPRETATION -- how sure the parser
is it correctly identified and categorized a requirement claim. This is
NEVER candidate evidence confidence, candidate proficiency, or job
importance (see `jobs.types.ParserConfidence`'s own docstring for the
full contrast with `evidence.types.ConfidenceLevel`).

A single small, centralized mapping by extraction "kind" -- not
scattered per-detector judgment calls.
"""
from __future__ import annotations

from gitscore.jobs.types import ParserConfidence

# A direct, unambiguous known-concept alias match, or an explicit numeric
# experience qualifier -- both come from clean, low-ambiguity pattern
# matches.
HIGH_CONFIDENCE_KINDS = frozenset({"resolved_concept", "experience_qualifier"})

# Requires more interpretive judgment: a conservative list-context
# unknown-term inference, or a curated non-technical phrase match.
MEDIUM_CONFIDENCE_KINDS = frozenset({"unresolved_concept_listed", "non_technical_pattern"})

# Explicitly ambiguous by construction -- an alternative/OR fallback
# claim (Part 14) never gets more than LOW confidence, since the parser
# deliberately declined to interpret which of several options applies.
LOW_CONFIDENCE_KINDS = frozenset({"alternative_fallback"})


def confidence_for(kind: str) -> ParserConfidence:
    if kind in HIGH_CONFIDENCE_KINDS:
        return ParserConfidence.HIGH
    if kind in MEDIUM_CONFIDENCE_KINDS:
        return ParserConfidence.MEDIUM
    if kind in LOW_CONFIDENCE_KINDS:
        return ParserConfidence.LOW
    raise ValueError(f"confidence_for: unknown extraction kind {kind!r}")
