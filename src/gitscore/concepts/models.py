"""Milestone 5C -- TechnicalConcept: a normalized technical concept.

TechnicalConcept represents a single, stable, machine-readable technical
idea (a language, framework, database, protocol, platform, ...)
independent of any job description or role. See
docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md Part 8 for the
architectural context this implements.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TechnicalConcept:
    """One canonical technical concept.

    `concept_id` is a stable, dotted, machine-readable identifier (e.g.
    "database.postgresql") -- never reused for a different concept and
    never deleted once shipped (see registry.py's versioning policy).

    `aliases` are the alternate human-typed spellings that should
    resolve to this concept (see registry.py / normalize.py for how
    they're matched) -- NOT free text to search for; matching always
    goes through the normalizer, never a raw string comparison against
    `display_name`.
    """

    concept_id: str
    display_name: str
    category: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    parent_id: str | None = None
    related_ids: tuple[str, ...] = field(default_factory=tuple)
    status: str = "active"
