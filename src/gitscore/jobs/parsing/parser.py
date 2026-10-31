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

**Milestone 9A -- requirement preservation:** fixes the high-severity
bug M8E identified ("Knowledge of Vue or Angular", "SPI, I2C, and UART"
silently producing ZERO `JobRequirement` rows -- not even a MISSING
marker). Two additive changes, both detailed in
`docs/evaluation/MILESTONE_9A_REQUIREMENT_PRESERVATION.md`:

1. `classify_alternative_claim()` and `find_conservative_unknown_terms()`
   now ALSO mint `unresolved:<term>` concept id(s) for an OR-list or
   enumeration-cue-introduced comma list with ZERO real confirmed
   concepts, provided every item is shaped like a specific named
   technology (`concepts.looks_like_specific_technology_name` --
   capitalization/acronym shape, never a vocabulary list). This is
   exactly what the pre-existing frozen gold fixtures
   (`evaluation/gold/jobs/frontend_01.json`,
   `embedded_firmware_01.json`, ...) already expected.
2. `_requirements_from_claim`'s new LAST-RESORT fallback (bottom of this
   function): if every detector above STILL produced nothing for a
   claim that carries one of three narrow structural signals
   (`_unresolved_requirement_signal` -- an "or", an enumeration-cue
   comma list, or a narrow technical lead-in phrase), emit exactly ONE
   `category="unresolved_requirement"` placeholder (`concept_id=None` --
   never fabricates a technology) instead of zero rows. This is the
   safety net for everything (1) still can't shape-confirm (e.g. "control
   systems or state estimation", "Experience with dbt").

Both changes are purely additive to claims that previously produced
ZERO requirement rows (or, for (1), where `any_confirmed` was already
`False`) -- a claim that already produced at least one row under the
pre-9A parser is completely unaffected.

**Milestone 10B -- safe section-state handling.** `_requirements_from_claim`
now short-circuits to `[]` when `infer_necessity()` returns `None`
(`jobs/parsing/necessity.py`) -- a claim admitted from text following
an unrecognized heading (`_SectionKind.UNKNOWN`, `segmentation.py`)
with no local REQUIRED/PREFERRED marker in its own text. See
`docs/evaluation/MILESTONE_10B_SECTION_STATE_SAFETY.md` for the full
design review: this removes the previous sticky-necessity-inheritance
failure mode (a stale REQUIRED/PREFERRED kind silently applying to
everything after an unrecognized heading) WITHOUT expanding the
heading-recognition vocabulary, WITHOUT a new diagnostic type (the
existing `UnparsedClaim` absorbs the newly-short-circuited claims), and
WITHOUT any `JobRequirement` schema, matcher, or scoring-formula
change. `JOB_DESCRIPTION_PARSER_VERSION` bumps `v4` -> `v5` accordingly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from gitscore.concepts.registry import default_registry, unresolved_concept_id
from gitscore.jobs.models import JobRequirement, SourceSpan
from gitscore.jobs.parsing.alternatives import classify_alternative_claim, contains_alternative_marker
from gitscore.jobs.parsing.concepts import (
    clean_list_fragment,
    contains_enumeration_cue,
    find_bare_short_alias_mentions,
    find_concept_mentions,
    find_conservative_unknown_terms,
)
from gitscore.jobs.parsing.confidence import confidence_for
from gitscore.jobs.parsing.dedup import deduplicate_requirements
from gitscore.jobs.parsing.experience import find_experience_qualifier
from gitscore.jobs.parsing.importance import infer_importance
from gitscore.jobs.parsing.necessity import infer_necessity
from gitscore.jobs.parsing.non_technical import find_non_technical_match
from gitscore.jobs.parsing.observability import observability_for_non_technical, observability_for_technical
from gitscore.jobs.parsing.segmentation import Claim, segment_description
from gitscore.jobs.profile import JobRequirementProfile

JOB_DESCRIPTION_PARSER_VERSION = "job_description_parser:v5"

# Milestone 9A -- a narrow, unambiguous technical lead-in used ONLY to
# gate the last-resort `unresolved_requirement` placeholder
# (`_unresolved_requirement_signal` below). Deliberately NOT the full
# `jobs.parsing.concepts._LIST_ITEM_PREFIXES` table: that table's bare
# filler alternatives ("with"/"using"/"in"/"and"/"or"/"strong"/"solid"/
# "advanced") are safe for stripping one word off an ALREADY-CONFIRMED
# list item, but far too weak a signal to single-handedly justify
# flagging an entire bare claim as an unresolved technical requirement
# (e.g. "Strong communication" must never match).
_TECHNICAL_LEAD_IN = re.compile(
    r"^(?:experience with|knowledge of|familiarity with|proficiency in|proficient in|expert in)\s+",
    re.IGNORECASE,
)


def _unresolved_requirement_signal(text: str) -> bool:
    """Milestone 9A -- is `text`'s structural shape strong enough to
    justify the last-resort `unresolved_requirement` placeholder (see
    `_requirements_from_claim`)? Exactly three, deliberately narrow
    shapes, never a general "contains a technical-sounding word" scan:

    1. An explicit alternative marker ("Vue or Angular", "control
       systems or state estimation").
    2. A comma list introduced by an enumeration cue ("...peripherals
       such as SPI, I2C, and UART").
    3. A single bare claim led by a narrow, unambiguous technical
       lead-in phrase, with a short, non-generic remainder
       ("Experience with dbt", "Familiarity with PLC programming").

    See docs/evaluation/MILESTONE_9A_REQUIREMENT_PRESERVATION.md for the
    concrete false-positive cases (ordinary responsibility prose like
    "Write clean, maintainable, and well-tested code", which has commas
    but no enumeration cue and no qualifying lead-in) this narrowness is
    built to exclude.
    """
    if contains_alternative_marker(text):
        return True
    if "," in text and contains_enumeration_cue(text):
        return True
    lead_in = _TECHNICAL_LEAD_IN.match(text)
    if lead_in is None:
        return False
    return clean_list_fragment(text[lead_in.end():]) is not None


def _requirements_from_claim(claim: Claim, registry) -> list[JobRequirement]:
    necessity = infer_necessity(claim.text, claim.necessity_hint)
    if necessity is None:
        # Milestone 10B -- the claim was admitted from an unrecognized
        # (UNKNOWN) section and carries no local REQUIRED/PREFERRED
        # marker in its own text, so no necessity can be responsibly
        # assigned. Returning [] here (rather than fabricating REQUIRED
        # or PREFERRED) routes the claim through `_parse`'s EXISTING
        # "zero requirements produced -> UnparsedClaim" fallback below --
        # no new diagnostic type, no JobRequirement schema change.
        return []
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

    safe_mentions = find_concept_mentions(claim.text, registry=registry)
    mentions = safe_mentions
    mention_confidence_kind = "resolved_concept"
    if not mentions:
        # Milestone 8D.1: a narrow, last-resort fallback for a concept
        # with NO readme-safe alias at all (today: bare "c") -- only
        # tried once the normal safe-alias scan finds nothing at all, so
        # it never competes with/overrides a direct alias match. See
        # `find_bare_short_alias_mentions`'s docstring for the full,
        # bounded gating policy.
        #
        # Deliberately NOT folded into `safe_mentions` below: the
        # comma-gated conservative unknown-term policy
        # (`find_conservative_unknown_terms`) requires an
        # already-CONFIRMED mention to fire at all, and that gate must
        # stay keyed on a real safe-alias match -- letting a bare-C
        # fallback match ALSO unlock it would let an unrelated,
        # comma-separated descriptive clause elsewhere in the same
        # sentence (e.g. "...embedded, resource-constrained
        # environments") get promoted to a fabricated unresolved
        # concept, which this bounded fallback must never cause as a
        # side effect.
        mentions = find_bare_short_alias_mentions(claim.text, registry=registry)
        if mentions:
            mention_confidence_kind = "bare_short_alias_context"

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
                parser_confidence=confidence_for(mention_confidence_kind),
                source_span=span,
            )
        )

    for term in find_conservative_unknown_terms(claim.text, safe_mentions):
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

    if not requirements and _unresolved_requirement_signal(claim.text):
        # Milestone 9A -- every detector above produced NOTHING for this
        # claim, yet it already survived segmentation's requirement gate
        # AND carries one of the narrow structural signals
        # `_unresolved_requirement_signal` checks for. Rather than let
        # the claim silently disappear with no row and no trace at all
        # (the M8E-identified high-severity bug this milestone fixes),
        # preserve exactly ONE conservative, non-fabricating placeholder:
        # `concept_id=None` (never invents a specific technology --
        # contrast the `unresolved:<term>` ids minted above, which DO
        # name a specific, if unregistered, technology once the parser
        # is confident enough one is actually being enumerated).
        # `concept_id=None` forces `MatchStatus.NOT_ASSESSABLE` in
        # `matching.engine.match_requirement` regardless of
        # `github_observability`, so this can never be scored SUPPORTED.
        requirements.append(
            JobRequirement(
                original_text=claim.text,
                necessity=necessity,
                importance=importance,
                github_observability=observability_for_non_technical("unresolved_requirement"),
                concept_id=None,
                category="unresolved_requirement",
                parser_confidence=confidence_for("unresolved_requirement_fallback"),
                source_span=span,
            )
        )

    return requirements


@dataclass(frozen=True)
class UnparsedClaim:
    """Milestone 9C -- one claim `segmentation.py` judged requirement-
    shaped (it survived the SAME conservative gate every real
    `JobRequirement` already passes through -- no new, looser trigger
    is introduced here) for which `_requirements_from_claim` STILL
    produced zero rows.

    Milestone 10B: this now ALSO covers a claim admitted from an
    unrecognized (`_SectionKind.UNKNOWN`) section with no local
    REQUIRED/PREFERRED marker in its own text -- `infer_necessity`
    returned `None`, and `_requirements_from_claim` short-circuits to
    `[]` before running any detector, for exactly the same reason: no
    responsible, non-fabricated row can be produced. This is a
    generalization of this class's existing meaning ("the parser could
    not responsibly produce a `JobRequirement` for this"), not a second,
    different kind of gap -- no new field, no new type.

    This is a strictly more severe gap than the `category=
    "unresolved_requirement"` placeholder (Milestone 9A): that
    placeholder means the parser recognized the claim as requirement-
    shaped and preserved a trace of it (a real `JobRequirement` row,
    `concept_id=None`, inspectable via `match_job()`/`assess_job()`).
    An `UnparsedClaim` means NOTHING was preserved at all -- there is no
    `JobRequirement`, no `RequirementMatch`, nothing for the matcher or
    assessment layer to ever see. `original_text`/`source_span` are
    retained so a caller can still show the user exactly what was
    missed, without inventing a concept, category, or observability
    for it (there is nothing here to attach a status to -- see
    `docs/evaluation/MILESTONE_9C_ASSESSMENT_TRANSPARENCY.md` for why
    this is reported as a plain text diagnostic rather than forced into
    the existing `MatchStatus`/`JobRequirement` shapes).

    Deliberately NOT part of `JobRequirementProfile` (which stays
    byte-for-byte unchanged, `JOB_REQUIREMENT_SCHEMA_VERSION` untouched)
    -- mirrors `evidence/extraction`'s own `ExtractionFailure` /
    `extractor_failures` precedent (Milestone 5D): a pipeline-level
    diagnostic, never domain state.
    """

    text: str
    source_span: SourceSpan


def _parse(
    description: str,
    *,
    title: str | None,
    company: str | None,
) -> tuple[JobRequirementProfile, tuple[UnparsedClaim, ...]]:
    """The one real parsing implementation -- shared, unchanged, by both
    `parse_job_description()` and `parse_job_description_with_diagnostics()`
    (Milestone 9C) so there is exactly one place this logic lives, never
    two independently-drifting copies.
    """
    registry = default_registry()
    claims = segment_description(description)

    all_requirements: list[JobRequirement] = []
    unparsed_claims: list[UnparsedClaim] = []
    for claim in claims:
        requirements = _requirements_from_claim(claim, registry)
        if not requirements:
            unparsed_claims.append(UnparsedClaim(text=claim.text, source_span=SourceSpan(claim.start, claim.end)))
        all_requirements.extend(requirements)

    deduplicated = deduplicate_requirements(all_requirements)

    profile = JobRequirementProfile(
        raw_text=description,
        requirements=deduplicated,
        parser_version=JOB_DESCRIPTION_PARSER_VERSION,
        title=title,
        company=company,
    )
    return profile, tuple(unparsed_claims)


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

    Byte-for-byte unchanged by Milestone 9C: every existing caller
    (including every `scripts/evaluate_*.py` harness) keeps calling this
    exact function with this exact signature and gets this exact return
    type back. See `parse_job_description_with_diagnostics()` for the
    new, additive sibling that also reports unparsed claims.
    """
    profile, _unparsed_claims = _parse(description, title=title, company=company)
    return profile


@dataclass(frozen=True)
class ParsedJobDescription:
    """Milestone 9C -- `parse_job_description()`'s result PLUS the
    pipeline-level diagnostic `parse_job_description()` itself never
    exposes. `profile` is byte-for-byte identical to what
    `parse_job_description(description, title=title, company=company)`
    would return for the same input -- this wrapper adds information,
    it never changes what the domain model contains.
    """

    profile: JobRequirementProfile
    unparsed_claims: tuple[UnparsedClaim, ...] = ()


def parse_job_description_with_diagnostics(
    description: str,
    *,
    title: str | None = None,
    company: str | None = None,
) -> ParsedJobDescription:
    """Milestone 9C -- the diagnostics-aware sibling of
    `parse_job_description()`, used by
    `gitscore.application.job_fit.analyze_job_fit()` so a caller that
    wants visibility into claims the parser could not interpret at all
    (distinct from the Milestone 9A `unresolved_requirement` placeholder,
    which DOES produce a real, inspectable `JobRequirement` row -- see
    `UnparsedClaim`'s own docstring) can get it, without changing
    `parse_job_description()`'s existing signature/behavior for every
    other caller.
    """
    profile, unparsed_claims = _parse(description, title=title, company=company)
    return ParsedJobDescription(profile=profile, unparsed_claims=unparsed_claims)
