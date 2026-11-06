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

**Milestone 10C -- real-world heading recognition.** `segmentation.py`'s
heading recognition widens from a small exact-phrase table to an
anchored, structural classifier (see that module's own docstring) that
also recognizes two new section purposes, `LEARNING` and a generalized
`NON_QUALIFICATION` (the existing `SKIP` kind, now reached by more
headings) -- entirely within `segmentation.py`; nothing in THIS module
changes except reusing `concepts.TECHNICAL_LEAD_IN` (moved, not
duplicated, from this module) and the version bump. `_requirements_from_claim`'s
`None`-necessity short-circuit (above) is unchanged and now also covers
claims admitted under `LEARNING`. See
`docs/evaluation/MILESTONE_10C_SECTION_CLASSIFICATION.md`.
`JOB_DESCRIPTION_PARSER_VERSION` bumps `v5` -> `v6` accordingly.

**Milestone 10D -- alternative-requirement semantics.**
`alternatives.py::classify_alternative_claim()` gains an explicit
ANY-of trigger-phrase path (Root Cause 4 -- "at least one programming
language (e.g., ...)" with no literal "or" at all) and an idiom guard
against reading "<number> or more" as a list separator (Root Cause 5
-- "one or more of the following programming languages: ..."), plus a
shape-gated fix to a previously-unconditional `unresolved:<term>`
promotion branch that could fabricate a garbled id from idiom-blind
splitting. Entirely within `alternatives.py` -- nothing in THIS module
changes except the version bump; `classify_alternative_claim()`'s
signature, return type, and every PREVIOUSLY-correct outcome are
unchanged (confirmed via the full regression suite,
`docs/evaluation/MILESTONE_10D_ALTERNATIVE_SEMANTICS.md`'s own 41
-control corpus, and re-runs of M9B/M10A/M10C). A MIXED AND/OR shape
("Python or Java and SQL") is explicitly NOT addressed by this
milestone -- deferred, see that document's Root Cause 6.
`JOB_DESCRIPTION_PARSER_VERSION` bumps `v6` -> `v7` accordingly.

**Milestone 10E -- narrative vs. applicant-qualification semantics.**
`_requirements_from_claim` now computes an "effective" necessity hint
via `jobs/parsing/necessity.py::resolve_necessity_hint` (new) BEFORE
calling the existing, unchanged `infer_necessity` -- closing the real
SOTI ("The technologies you learn... languages like C#, or deepening
your knowledge of databases by leveraging SQL...", fabricated into a
scored `(language.csharp, language.sql)` alternative-group requirement)
and Manulife ("Collaborate with engineering and business teams to build
user-focused solutions.", a RESPONSIBILITY bullet fabricated into a
scored `category='soft_skill'` requirement) false positives found by
that milestone's own evaluation-first review
(`docs/evaluation/MILESTONE_10E_NARRATIVE_REQUIREMENT_SEMANTICS.md`).
`resolve_necessity_hint` only ever NARROWS a hint to `None` or passes it
through unchanged -- an explicit local REQUIRED/PREFERRED marker in a
claim's own text always wins first, unconditionally, exactly as before;
every previously-correct case (an explicit qualification anywhere, a
genuine REQUIRED/PREFERRED section, a genuinely unsectioned posting)
is unaffected, confirmed via the 51-control M10E corpus and zero
regressions on every pre-existing frozen evaluation corpus
(M9B/M10A/M10C/M10D/8c:v1/8c:v1.1). `segment_description`'s own
admission/heading-recognition/necessity-hint-computation logic, and
every other detector in this module, are untouched. `JOB_DESCRIPTION_PARSER_VERSION`
bumps `v7` -> `v8` accordingly.

**Milestone 11-A1 -- narrow fabrication safety fixes.** Two small,
independently-approved fixes, found during Milestone 11's broader
evaluation-first generalization review
(`docs/evaluation/MILESTONE_11_GENERALIZABLE_JOB_UNDERSTANDING.md`),
entirely within `jobs/parsing/concepts.py` and `jobs/parsing/narrative.py`
-- nothing in THIS module changes except the version bump.
`concepts.py::_consider_fragment` (the sibling-confirmed branch of
`find_conservative_unknown_terms`) now requires a MULTI-WORD leftover
fragment to also pass `looks_like_specific_technology_name` before
promotion -- single-word fragments remain exempt (Python-package
naming convention is lowercase: `numpy`, `pandas`). `narrative.py`'s
`_COMPANY_NARRATIVE_CUE` gains one new, narrow, employer-agnostic
alternative for `"our ... backend/frontend/codebase/infrastructure"`
phrasing. See `docs/CHANGELOG_DEV.md`'s Milestone 11-A1 entry for the
full before/after. `JOB_DESCRIPTION_PARSER_VERSION` bumps `v8` -> `v9`
accordingly.

**Milestone 11-A2 -- line-wrap segmentation integrity.** Two
coordinated fixes, found while tracing M11-A1's own disclosed residual
limitation
(`docs/evaluation/MILESTONE_11_A2_LINE_WRAP_INTEGRITY.md`), entirely
within `jobs/parsing/segmentation.py`, `jobs/parsing/narrative.py`, and
`jobs/parsing/necessity.py` -- nothing in THIS module changes except
the version bump. `segment_description()` now extends an ordinary
line's content span across any immediately-following soft-wrap-
continued line (comma/semicolon-ending, or ending in a closed,
generic English function-word/copula-verb/contraction vocabulary --
never a technology/employer-specific term), always stopping at a
heading, a bullet-prefixed line, or a blank-line paragraph gap,
via direct slicing of the original `description` (no rewritten
string, no offset-mapping table). `narrative.py`'s/`necessity.py`'s
own cue/marker regexes had every literal single-space word separator
widened to `\\s+`, so a phrase now spanning a reconstructed multi-line
`Claim`'s embedded newline is still recognized exactly as it would be
with an ordinary space. Together these close the real residual
fabrication M11-A1 left (`"We've\nbuilt our platform on Go and
PostgreSQL..."`, previously 3 spurious rows from one company-narrative
sentence, now 0) -- a SECOND, disclosed residual fabrication class
(a line ending in an ordinary content word with no comma/semicolon/
function-word, e.g. "...for this role — however,\nwe are also open to...
with strong\nfundamentals...") is explicitly NOT solved by this
milestone (a length- or part-of-speech-based heuristic was evaluated
and rejected -- see that document's §3/§5.3 for the concrete
counter-example this finding is based on, not merely asserted).
`JOB_DESCRIPTION_PARSER_VERSION` bumps `v9` -> `v10` accordingly.

**Milestone 11-G6 -- heading-classification correctness.** A narrow,
label-only-to-this-module version bump: the actual fix is entirely
within `jobs/parsing/segmentation.py`'s `_matched_heading_families()`
(see that module's own docstring and
`docs/evaluation/MILESTONE_11_G6_HEADING_CLASSIFICATION.md`) -- a new,
generic `_CANDIDATE_PROFILE_ROOT` vocabulary excludes a false
`_SectionKind.SKIP` match on genuine candidate-profile headings like
"Who We Are Looking For:" that previously collided with the
`NON_QUALIFICATION` family's unanchored `\bwho we are\b` substring
match. Nothing in THIS module changes except the version bump.
`JOB_DESCRIPTION_PARSER_VERSION` bumps `v10` -> `v11` accordingly.

**Milestone 11-G7 -- section-boundary integrity.** Another narrow,
label-only-to-this-module version bump: the actual fix is entirely
within `jobs/parsing/segmentation.py`'s `_classify_heading_line()` (see
that module's own docstring and
`docs/evaluation/MILESTONE_11_G7_SECTION_BOUNDARY_INTEGRITY.md`) -- the
word-count shape gate now branches on signal strength (14 words for
colon/ALL-CAPS/Markdown-terminated lines, the unchanged 7 for bare
title-case lines) instead of applying one fixed limit uniformly,
fixing a confirmed defect where a genuine long heading going
unrecognized could let a stale section state leak across the boundary
-- in the worst cases, fabricating a scored `JobRequirement` from
responsibility prose, or silently suppressing a genuine REQUIRED
qualification entirely. Nothing in THIS module changes except the
version bump. `JOB_DESCRIPTION_PARSER_VERSION` bumps `v11` -> `v12`
accordingly.
"""
from __future__ import annotations

from dataclasses import dataclass

from gitscore.concepts.registry import default_registry, unresolved_concept_id
from gitscore.jobs.models import JobRequirement, SourceSpan
from gitscore.jobs.parsing.alternatives import classify_alternative_claim, contains_alternative_marker
from gitscore.jobs.parsing.concepts import (
    TECHNICAL_LEAD_IN,
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
from gitscore.jobs.parsing.necessity import infer_necessity, resolve_necessity_hint
from gitscore.jobs.parsing.non_technical import find_non_technical_match
from gitscore.jobs.parsing.observability import observability_for_non_technical, observability_for_technical
from gitscore.jobs.parsing.segmentation import Claim, document_has_any_recognized_heading, segment_description
from gitscore.jobs.profile import JobRequirementProfile

JOB_DESCRIPTION_PARSER_VERSION = "job_description_parser:v12"


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
    lead_in = TECHNICAL_LEAD_IN.match(text)
    if lead_in is None:
        return False
    return clean_list_fragment(text[lead_in.end():]) is not None


def _requirements_from_claim(
    claim: Claim, registry, *, document_has_recognized_heading: bool
) -> list[JobRequirement]:
    # Milestone 10E -- `resolve_necessity_hint` narrows `claim.necessity_hint`
    # (never widens it -- see that function's own docstring) based on
    # section origin (`claim.section_kind`) and narrative-cue content,
    # BEFORE the existing, unchanged `infer_necessity` ever runs. An
    # explicit local REQUIRED/PREFERRED marker in `claim.text` always
    # wins regardless of this step (both functions check it first).
    effective_hint = resolve_necessity_hint(
        claim.text,
        claim.necessity_hint,
        section_kind=claim.section_kind,
        document_has_recognized_heading=document_has_recognized_heading,
    )
    necessity = infer_necessity(claim.text, effective_hint)
    if necessity is None:
        # Milestone 10B -- the claim was admitted from an unrecognized
        # (UNKNOWN) section and carries no local REQUIRED/PREFERRED
        # marker in its own text, so no necessity can be responsibly
        # assigned. Milestone 10E: this now ALSO covers a
        # RESPONSIBILITY/LEARNING claim, or a `None`-section claim that
        # precedes the same document's own later real sections, or a
        # narrative-cue claim in an otherwise-eligible context -- see
        # `resolve_necessity_hint`'s own docstring. Returning [] here
        # (rather than fabricating REQUIRED or PREFERRED) routes the
        # claim through `_parse`'s EXISTING "zero requirements produced
        # -> UnparsedClaim" fallback below -- no new diagnostic type, no
        # JobRequirement schema change.
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
    document_has_recognized_heading = document_has_any_recognized_heading(description)

    all_requirements: list[JobRequirement] = []
    unparsed_claims: list[UnparsedClaim] = []
    for claim in claims:
        requirements = _requirements_from_claim(
            claim, registry, document_has_recognized_heading=document_has_recognized_heading
        )
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
