"""Milestone 6B Part 9 -- GitHub observability policy.

Centralized, data-driven lookup tables -- NEVER `if concept == ...:
observability = ...` scattered through parser code. Observability is a
property of the REQUIREMENT TYPE, not of any specific candidate's
evidence (Milestone 6A's own design: whether GitHub can plausibly speak
to a claim at all, independent of whether this candidate happens to
show it).

Technical requirements: every category currently in the concept registry
(language, database, ml_framework, frontend_framework, backend_framework,
orm, infrastructure, cloud, platform, robotics, embedded,
hardware_description, compiler_toolchain, data_library) is a concrete,
directly-demonstrable technology, so a resolved OR unresolved technical
concept mention defaults to `STRONGLY_OBSERVABLE` uniformly. This is
intentionally a single constant today, not a per-category table --
documented here as the extension point if a future concept category ever
needs a different default (none currently do).

Non-technical requirements: looked up by the free-form `category` label
(Milestone 6A Part 6 / 6B `non_technical.py` /
`jobs/parsing/alternatives.py`) against a small table. An unrecognized
category defaults to `NOT_OBSERVABLE` -- the safe direction: never
silently overclaim that GitHub can verify something.
"""
from __future__ import annotations

from gitscore.jobs.types import GithubObservability

TECHNICAL_DEFAULT_OBSERVABILITY = GithubObservability.STRONGLY_OBSERVABLE

NON_TECHNICAL_CATEGORY_OBSERVABILITY: dict[str, GithubObservability] = {
    "experience": GithubObservability.NOT_OBSERVABLE,
    "education": GithubObservability.NOT_OBSERVABLE,
    "legal": GithubObservability.NOT_OBSERVABLE,
    "soft_skill": GithubObservability.NOT_OBSERVABLE,
    "leadership": GithubObservability.PARTIALLY_OBSERVABLE,
    "alternative_requirement": GithubObservability.PARTIALLY_OBSERVABLE,
}
NON_TECHNICAL_DEFAULT_OBSERVABILITY = GithubObservability.NOT_OBSERVABLE


def observability_for_technical() -> GithubObservability:
    return TECHNICAL_DEFAULT_OBSERVABILITY


def observability_for_non_technical(category: str | None) -> GithubObservability:
    if category is None:
        return NON_TECHNICAL_DEFAULT_OBSERVABILITY
    return NON_TECHNICAL_CATEGORY_OBSERVABILITY.get(category, NON_TECHNICAL_DEFAULT_OBSERVABILITY)
