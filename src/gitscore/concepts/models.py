"""Milestone 5C -- TechnicalConcept: a normalized technical concept.

TechnicalConcept represents a single, stable, machine-readable technical
idea (a language, framework, database, protocol, platform, ...)
independent of any job description or role. See
docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md Part 8 for the
architectural context this implements.

Milestone 5D.1 -- source-aware alias safety: `aliases` remains the ONE
list `resolve_concept()` matches against for every STRUCTURED source
(dependency manifests, GitHub language stats) -- those contexts hand
this code an already-scoped, already-intentional term (a package.json
key, a language-stats name), so any registered alias is safe there.
Free-form prose (README text) is a different matching context: a short
or ordinary-English alias ("go", "next", "js") that's perfectly
unambiguous as a package name or language-stats value collides
constantly with normal sentences. `readme_unsafe_aliases` marks exactly
the subset of `aliases` that must be excluded from that one context,
without removing them from `aliases` itself (they stay valid for
resolve_concept()/structured sources) -- see
`evidence/extraction/readme.py`, which is the ONLY caller of
`readme_safe_aliases()`.
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

    `readme_unsafe_aliases` is a subset of `aliases`: entries that are
    valid for structured-source resolution (`resolve_concept()`, used by
    dependency manifests and language stats) but must NOT be used to
    match free-form README prose, because they are short and/or ordinary
    English words that would otherwise produce false-positive evidence
    (see `readme_safe_aliases()` and `evidence/extraction/readme.py`).
    Empty by default -- most aliases are unambiguous enough to be safe
    everywhere.
    """

    concept_id: str
    display_name: str
    category: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    readme_unsafe_aliases: frozenset[str] = field(default_factory=frozenset)
    parent_id: str | None = None
    related_ids: tuple[str, ...] = field(default_factory=tuple)
    status: str = "active"

    def __post_init__(self) -> None:
        unknown = self.readme_unsafe_aliases - set(self.aliases)
        if unknown:
            raise ValueError(
                f"{self.concept_id}: readme_unsafe_aliases {sorted(unknown)} "
                "not present in aliases"
            )

    def readme_safe_aliases(self) -> tuple[str, ...]:
        """This concept's aliases minus `readme_unsafe_aliases`.

        Used exclusively by the README extractor -- structured sources
        (dependency manifests, language stats) resolve through the full
        `aliases` list via `resolve_concept()` and are unaffected. A
        concept whose only alias(es) are all readme-unsafe (e.g.
        `language.c`'s bare "c") returns an empty tuple: it can still be
        detected via language stats or a dependency, just never via a
        README mention -- prefer precision over guessing at prose.
        """
        return tuple(alias for alias in self.aliases if alias not in self.readme_unsafe_aliases)
