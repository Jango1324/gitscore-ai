"""Milestone 6B/6B.1 -- parse_job_description(): the ONLY orchestrating
entry point in this package.

    Raw Job Description
            |
            v
    segment_description()            (segmentation.py, Part 3)
            |
            v
    per claim: classify_alternative_claim()
       "technical"     -> ONE JobRequirement, alternative_concept_ids set
       "unsafe"        -> ONE conservative non-technical fallback
       "not_technical" -> concept mentions -> unknown terms ->
                          experience qualifier -> non-technical pattern
    (alternatives.py, concepts.py, experience.py, non_technical.py)
            |
            v
    necessity / importance / observability / parser confidence
    (necessity.py, importance.py, observability.py, confidence.py)
            |
            v
    deduplicate_requirements()        (dedup.py, Part 13)
            |
            v
    JobRequirementProfile              (jobs/profile.py -- alternative_concept_ids added in 6B.1)

Purely deterministic and rule-based (no LLM, no external API) -- see
`docs/ARCHITECTURE.md`'s Milestone 6B section for the explicit A/B/C
evaluation this design decision is based on, and where a future LLM
extraction adapter could plug into this same pipeline (replacing/
augmenting the claim-interpretation step) without changing
`JobRequirementProfile`'s shape.

**Milestone 6B.1:** an OR-shaped claim ("Python or Go") no longer
collapses into a text-only placeholder (6B's Option A) -- when the
parser can safely establish the alternatives are technical,
`classify_alternative_claim()` (`alternatives.py`) returns their
concept ids and this module builds ONE `JobRequirement` with
`alternative_concept_ids` populated instead of `concept_id`. The old
conservative placeholder (`category="alternative_requirement"`) is now
reserved for the narrower "confirmed technical context, but not ALL
alternatives could be safely represented" case; a claim with NO
confirmed technical concept anywhere in its OR-list (e.g. "Bachelor's
degree ... or a related field") is not treated as alternative-shaped at
all -- it flows through the exact same pipeline as any other claim.
"""
from __future__ import annotations

from gitscore.concepts.registry import default_registry, unresolved_concept_id
from gitscore.jobs.models import JobRequirement, SourceSpan
from gitscore.jobs.parsing.alternatives import classify_alternative_claim
from gitscore.jobs.parsing.concepts import find_concept_mentions, find_conservative_unknown_terms
from gitscore.jobs.parsing.confidence import confidence_for
from gitscore.jobs.parsing.dedup import deduplicate_requirements
from gitscore.jobs.parsing.experience import find_experience_qualifier
from gitscore.jobs.parsing.importance import infer_importance
from gitscore.jobs.parsing.necessity import infer_necessity
from gitscore.jobs.parsing.non_technical import find_non_technical_match
from gitscore.jobs.parsing.observability import observability_for_non_technical, observability_for_technical
from gitscore.jobs.parsing.segmentation import Claim, segment_description
from gitscore.jobs.profile import JobRequirementProfile

JOB_DESCRIPTION_PARSER_VERSION = "job_description_parser:v2"


def _requirements_from_claim(claim: Claim, registry) -> list[JobRequirement]:
    necessity = infer_necessity(claim.text, claim.necessity_hint)
    importance = infer_importance(claim.text, necessity)
    span = SourceSpan(claim.start, claim.end)

    alternative = classify_alternative_claim(claim.text, registry=registry)

    if alternative.kind == "technical":
        # Milestone 6B.1: ONE logical requirement, structured semantics --
        # the future matcher evaluates supported(A) OR supported(B)
        # directly from alternative_concept_ids, never by re-parsing
        # original_text.
        return [
            JobRequirement(
                original_text=claim.text,
                necessity=necessity,
                importance=importance,
                github_observability=observability_for_technical(),
                alternative_concept_ids=alternative.concept_ids,
                parser_confidence=confidence_for("resolved_concept"),
                source_span=span,
            )
        ]

    if alternative.kind == "unsafe":
        # Confirmed technical context, but at least one alternative could
        # not be safely represented -- fall back to the conservative,
        # non-technical placeholder rather than either dropping an
        # alternative or manufacturing a reckless unresolved id.
        return [
            JobRequirement(
                original_text=claim.text,
                necessity=necessity,
                importance=importance,
                github_observability=observability_for_non_technical("alternative_requirement"),
                concept_id=None,
                category="alternative_requirement",
                parser_confidence=confidence_for("alternative_fallback"),
                source_span=span,
            )
        ]

    # alternative.kind == "not_technical": no confirmed technology
    # anywhere in the OR-list (or no "or" at all) -- run the claim
    # through the exact same pipeline as any other claim.
    requirements: list[JobRequirement] = []

    mentions = find_concept_mentions(claim.text, registry=registry)
    seen_concept_ids: set[str] = set()
    for mention in mentions:
        if mention.concept_id in seen_concept_ids:
            continue
        seen_concept_ids.add(mention.concept_id)
        concept = registry.get(mention.concept_id)
        requirements.append(
            JobRequirement(
                original_text=claim.text,
                necessity=necessity,
                importance=importance,
                github_observability=observability_for_technical(),
                concept_id=mention.concept_id,
                category=concept.category if concept is not None else None,
                parser_confidence=confidence_for("resolved_concept"),
                source_span=span,
            )
        )

    for term in find_conservative_unknown_terms(claim.text, mentions):
        concept_id = unresolved_concept_id(term)
        if concept_id in seen_concept_ids:
            continue
        seen_concept_ids.add(concept_id)
        requirements.append(
            JobRequirement(
                original_text=claim.text,
                necessity=necessity,
                importance=importance,
                github_observability=observability_for_technical(),
                concept_id=concept_id,
                category=None,
                parser_confidence=confidence_for("unresolved_concept_listed"),
                source_span=span,
            )
        )

    if find_experience_qualifier(claim.text) is not None:
        requirements.append(
            JobRequirement(
                original_text=claim.text,
                necessity=necessity,
                importance=importance,
                github_observability=observability_for_non_technical("experience"),
                concept_id=None,
                category="experience",
                parser_confidence=confidence_for("experience_qualifier"),
                source_span=span,
            )
        )

    non_technical = find_non_technical_match(claim.text)
    if non_technical is not None:
        category, _ = non_technical
        requirements.append(
            JobRequirement(
                original_text=claim.text,
                necessity=necessity,
                importance=importance,
                github_observability=observability_for_non_technical(category),
                concept_id=None,
                category=category,
                parser_confidence=confidence_for("non_technical_pattern"),
                source_span=span,
            )
        )

    return requirements


def parse_job_description(
    description: str,
    *,
    title: str | None = None,
    company: str | None = None,
) -> JobRequirementProfile:
    """Parse raw job-description text into a `JobRequirementProfile`
    (Milestone 6A's existing, UNCHANGED domain model -- no second,
    parallel job schema).

    `description` is preserved verbatim as `JobRequirementProfile.raw_text`
    regardless of what was or wasn't extracted from it (Part 2). An
    empty/whitespace-only `description` raises `ValueError` -- via
    `JobRequirementProfile.__post_init__`'s existing invariant, not a
    duplicated check here.
    """
    registry = default_registry()
    claims = segment_description(description)

    all_requirements: list[JobRequirement] = []
    for claim in claims:
        all_requirements.extend(_requirements_from_claim(claim, registry))

    deduplicated = deduplicate_requirements(all_requirements)

    return JobRequirementProfile(
        raw_text=description,
        requirements=deduplicated,
        parser_version=JOB_DESCRIPTION_PARSER_VERSION,
        title=title,
        company=company,
    )
