"""Milestone 6B Part 15 -- experience-qualifier recognition.

Recognizes explicit numeric experience constraints ("3+ years of Python
experience", "5 years of software development experience") ONLY well
enough to avoid losing them -- never sophisticated CV/resume
verification. A match here always becomes a non-technical requirement
(`concept_id=None`, `category="experience"`), kept strictly separate
from whatever technical concept the SAME sentence might also mention
(Milestone 6A Part 1's central example: "3+ years of experience building
Python backend services" must produce a Python requirement AND a
professional-experience requirement, never one claim conflating both).
"""
from __future__ import annotations

import re

# The CORE trigger is a bare numeric years-count ("3+ years", "5 years",
# "2+ years") -- sufficient by itself (e.g. "2+ years working with
# Kubernetes" never says the word "experience" at all, but is obviously
# an experience qualifier). When the word "experience" follows shortly
# after (optionally through "of" and up to a few descriptive words --
# "of Python experience", "of software development experience"), the
# captured span is extended to include it for a more complete/readable
# `original_text`; otherwise the bare years-count span is used as-is.
_YEARS_CORE = re.compile(r"\b\d+\+?\s*(?:-\s*\d+)?\+?\s*years?\b", re.IGNORECASE)
_TRAILING_EXPERIENCE = re.compile(r"^\s*(?:of\s+)?(?:[A-Za-z]+\s+){0,3}?experience\b", re.IGNORECASE)


def find_experience_qualifier(text: str) -> tuple[int, int] | None:
    """The span of an explicit numeric experience qualifier in `text`,
    or `None` if there isn't one. Returns only the FIRST match -- one
    experience claim per source claim is sufficient for this milestone's
    scope (a sentence stating two different numeric experience
    requirements independently is not a case this MVP handles specially).
    """
    match = _YEARS_CORE.search(text)
    if match is None:
        return None
    start, end = match.start(), match.end()
    tail = text[end:end + 40]
    trailing = _TRAILING_EXPERIENCE.match(tail)
    if trailing is not None:
        end += trailing.end()
    return start, end
