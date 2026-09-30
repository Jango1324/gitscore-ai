"""Milestone 6B Part 13 -- requirement deduplication.

A real job posting restates the same requirement across sections (e.g.
"Strong Python skills" under Requirements AND "Build Python backend
services" under Responsibilities) -- both assert the exact same
technical fact ("Python is required") and collapsing them to one row is
correct; the future matcher has no use for two rows saying the same
thing. The dedup KEY is deliberately narrower than "identical
JobRequirement" (which `JobRequirementProfile` itself already rejects as
malformed input, Milestone 6A):

- Technical requirements: `(concept_id, necessity)` -- two claims
  asserting "language.python is REQUIRED" collapse to one, regardless of
  which sentence said so.
- Alternative-group requirements (Milestone 6B.1):
  `(alternative_concept_ids, necessity)` -- since `JobRequirement`
  itself stores `alternative_concept_ids` SORTED (its own `__post_init__`
  invariant), "Python or Go" and "Go or Python" produce the IDENTICAL
  key and collapse to one, exactly the "tuple ordering must not
  accidentally change logical identity" requirement -- for free, with no
  set-vs-tuple special-casing needed here.
- Non-technical requirements: `(category, necessity, normalized_text)` --
  deliberately narrower on TEXT too, so "3+ years of professional
  experience" and "5 years of professional Python experience" do NOT
  collapse into each other (different text, both preserved) even though
  both are `category="experience"`. This is exactly what keeps "Python
  required" and "5 years professional Python experience" from losing
  their DIFFERENT claims (Part 13's own example): the technical Python
  sub-claim from the second sentence dedupes against the first (same
  technical fact), but the non-technical experience sub-claim it also
  produces has no matching key anywhere else, so it survives untouched.

When two requirements share a dedup key, the one with the HIGHER
`importance` is kept (a stronger-emphasis restatement is more
informative for a future matcher than a plain first-mention) -- ties
keep the first occurrence. Output order follows first occurrence of each
surviving key, never re-sorted otherwise.
"""
from __future__ import annotations

from gitscore.jobs.models import JobRequirement


def _dedup_key(requirement: JobRequirement):
    if requirement.is_alternative_group:
        return ("technical_alternative", requirement.alternative_concept_ids, requirement.necessity)
    if requirement.is_technical:
        return ("technical", requirement.concept_id, requirement.necessity)
    return (
        "non_technical",
        requirement.category,
        requirement.necessity,
        requirement.original_text.strip().lower(),
    )


def deduplicate_requirements(requirements) -> tuple[JobRequirement, ...]:
    best_by_key: dict[object, JobRequirement] = {}
    first_index_by_key: dict[object, int] = {}

    for index, requirement in enumerate(requirements):
        key = _dedup_key(requirement)
        first_index_by_key.setdefault(key, index)
        current_best = best_by_key.get(key)
        if current_best is None or requirement.importance > current_best.importance:
            best_by_key[key] = requirement

    ordered_keys = sorted(first_index_by_key, key=lambda key: first_index_by_key[key])
    return tuple(best_by_key[key] for key in ordered_keys)
