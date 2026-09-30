"""Milestone 6B Part 10 -- non-technical requirement recognition.

A small, curated table of GENERIC HR/qualification boilerplate phrases
that appear across virtually every technical job posting regardless of
domain (education, communication, work authorization, leadership) --
never a technology name, so this table is not a "role-specific parser"
in the sense the milestone forbids: it recognizes universal posting
structure, not domain content. Matches always become a non-technical
`JobRequirement` (`concept_id=None`).
"""
from __future__ import annotations

import re

# (category, compiled pattern) -- order matters only in that the FIRST
# matching category wins if a sentence somehow matches more than one
# (rare; each pattern targets a distinct phrase family).
_PATTERNS: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    (
        "education",
        re.compile(
            r"\bbachelor'?s?\b|\bmaster'?s?\b|\bph\.?d\.?\b|\bdegree\b",
            re.IGNORECASE,
        ),
    ),
    (
        "legal",
        re.compile(
            r"\beligible to work\b|\bwork authorization\b|\bwork permit\b|"
            r"\bvisa sponsorship\b|\blegally authorized\b|\bsecurity clearance\b",
            re.IGNORECASE,
        ),
    ),
    (
        "leadership",
        re.compile(
            r"\bmentor\w*\b|\bleadership\b|\bmanage\w* (?:a team|other engineers)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "soft_skill",
        re.compile(
            r"\bcommunication skills\b|\bwritten and verbal\b|\binterpersonal skills\b|"
            r"\bteamwork\b|\bcross-functional team\b|\bcollaborat\w*\b",
            re.IGNORECASE,
        ),
    ),
)


def find_non_technical_match(text: str) -> tuple[str, tuple[int, int]] | None:
    """The (category, span) of the first non-technical phrase family
    matched in `text`, or `None`.
    """
    for category, pattern in _PATTERNS:
        match = pattern.search(text)
        if match is not None:
            return category, (match.start(), match.end())
    return None
