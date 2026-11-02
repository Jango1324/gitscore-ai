"""Milestone 11-B Stage 2B -- Path A compatibility adapter.

Converts an EXISTING, already-produced `JobRequirement`/`UnparsedClaim`
(Milestone 6A/9C) into a `Qualification` (Milestone 11-B Stage 1) and
back, and exists ONLY to validate that the Stage 1 representation can
express what today's parser already produces -- see
`docs/evaluation/MILESTONE_11_B_STAGE_2A_SHADOW_INTEGRATION.md`'s own
Phase 2 ("Path A: Compatibility adapter... validates compatibility
only") for the full rationale this module implements.

**Standalone, exactly like `qualification.py` itself.** Nothing in
`parser.py`/`segmentation.py`/`necessity.py`/`narrative.py`/
`confidence.py`/`observability.py`/`non_technical.py` imports this
module -- confirmed by a dedicated test, not merely intended. Building
this adapter changes nothing about what the live parser produces for
any real job description.

**This module NEVER improves recall.** Every `Qualification` it
produces is a RESTATEMENT of a `JobRequirement`/`UnparsedClaim` that
already existed; it never classifies text the live parser did not
already classify.

## Revision history (Stage 2B hardening)

The first version of this module achieved round-trip equality on seven
named fields (`original_text`, `source_span`, `necessity`,
`concept_id`/`alternative_concept_ids`, `github_observability`,
`parser_confidence`) but NOT on two more (`importance`, `category`'s
raw string) -- `project_qualification()` has no way to reconstruct
either, since `Qualification` carries no `importance` field at all and
always writes back `category=qualification_kind.value`, never the
original registry/phrase string. A correction request held commit on
that version specifically because "full `JobRequirement` dataclass
equality" is the real bar, not a hand-picked field subset -- and
because one measured, concrete consequence of the `category` gap (the
two existing `_UNPARSED_PLACEHOLDER_CATEGORIES` strings both collapsing
to `"other_legitimate"`, changing `api/serialization.py`'s own
`interpretation_status` from `"unparsed_placeholder"` to
`"non_technical"`) is a real behavior change if this adapter's output
were ever read by anything downstream, not merely an abstract gap.

**Three fix shapes were weighed:**

- **(B) Add `importance`/a raw-category field directly onto
  `Qualification`.** Rejected: `Qualification` is Stage 1's own,
  separately committed and approved model, whose field set was an
  explicit, documented design decision ("the mission's own Phase 1
  dimension list never named [importance]" --
  `_STAGE_1_PLACEHOLDER_IMPORTANCE`'s own prior docstring). Broadening
  it now, to fix an ADAPTER problem, would reopen and reverse an
  already-approved decision outside this correction's own scope, and
  would be the kind of "unapproved public model change" a genuine
  architectural-tradeoff STOP should be raised for -- avoided here
  because a smaller fix exists (below) that needs no such change.
- **(C) Report every requirement whose `importance != MEDIUM` or whose
  `category` isn't `"education"`/`"experience"` as
  `UnsupportedAdapterCase`, rather than returning a changed object.**
  Technically sound (never presents a changed object as a successful
  reconstruction) but measured, in the PRIOR version's own harness run,
  to affect 237/265 requirements (89%) -- nearly the entire corpus.
  Reporting "the compatibility adapter cannot represent 89% of today's
  requirements" would be an honest number, but it throws away
  information this adapter CAN actually preserve with a smaller fix,
  and would make Path A nearly useless for its stated validation
  purpose. Not used alone, for that reason -- but its SPIRIT (never
  silently present a changed object as success) is kept: a
  `JobRequirement` that genuinely cannot be reconstructed at all (the
  pre-existing `missing_source_span` case) still raises
  `UnsupportedAdapterCase`, explicitly, exactly as before.
- **(A) A typed compatibility envelope, `AdaptedQualification`,
  carrying the Stage-1 `Qualification` PLUS the two legacy scalar
  values (`legacy_importance`, `legacy_category`) verbatim, defined
  entirely in THIS adapter module.** Chosen. `Qualification`,
  `JobRequirement`, and `UnparsedClaim` are all completely unchanged --
  `AdaptedQualification` is a brand-new, adapter-internal type, never
  imported by production code, never exposed via the API, the matcher,
  or scoring. Reconstruction (`job_requirement_from_adapted()`) calls
  the EXISTING, unmodified `project_qualification()` first (so every
  Stage 1 safety rule still applies unchanged), then patches the two
  legacy scalars back onto the result via `dataclasses.replace()` --
  never inventing a value, never equating `category` with
  `qualification_kind`, never normalizing away a placeholder category's
  own identity. This achieves **full `JobRequirement` dataclass
  equality** for every one of the 265 requirements the Stage 2B harness
  exercises (confirmed by re-running it after this change), without any
  public schema change anywhere.

`UnparsedClaim` needed no envelope: it carries exactly two fields
(`text`, `source_span`), both already round-tripped exactly by the
PRIOR version, confirmed again below.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from gitscore.jobs.models import JobRequirement
from gitscore.jobs.parsing.parser import UnparsedClaim
from gitscore.jobs.parsing.qualification import (
    LogicalComposition,
    NormalizedReference,
    Qualification,
    QualificationKind,
    project_qualification,
)
from gitscore.jobs.types import Importance

# Milestone 11-B Stage 2B -- the closed, already-existing category
# vocabulary `non_technical.py`/`experience.py` produce (see Stage 2A
# §1.10). Never widened here: a category string outside these three
# buckets (including the two placeholder categories,
# `"alternative_requirement"`/`"unresolved_requirement"`, and a bare
# `None`) falls through to `OTHER_LEGITIMATE` below -- today's own
# conservative, non-fabricating shape, never a confident
# technology/education/experience/nontechnical claim. This mapping
# is used ONLY to pick `qualification_kind` (an internal, structural
# classification) -- it is NEVER equated with `category` itself, which
# `AdaptedQualification.legacy_category` preserves completely
# separately and verbatim.
_EDUCATION_CATEGORY = "education"
_EXPERIENCE_CATEGORY = "experience"
_NONTECHNICAL_CATEGORIES = frozenset({"legal", "leadership", "soft_skill"})


@dataclass
class UnsupportedAdapterCase(Exception):
    """Raised when an EXISTING `JobRequirement`/`UnparsedClaim` carries
    information that genuinely cannot be represented at all -- e.g. a
    hand-constructed `JobRequirement` with `source_span=None` (optional
    on `JobRequirement`, required on `Qualification` -- see
    `jobs/models.py`'s own field default). Distinguishes "this specific
    input cannot be adapted at all" from "the adapter ran, but the
    reconstruction differs" -- the latter should no longer occur at all
    for a `JobRequirement` produced by the real parser, per this
    module's own Stage 2B hardening (see module docstring).

    `reason`: a short, stable, test-matchable string (mirrors
    `ProjectionResult.unsafe_reason`'s own convention).
    `detail`: a free-text human-readable explanation, never machine-parsed.
    """

    reason: str
    detail: str

    def __str__(self) -> str:
        return f"{self.reason}: {self.detail}"


@dataclass(frozen=True)
class AdaptedQualification:
    """A `Qualification` PLUS the two legacy `JobRequirement` scalars
    `project_qualification()` cannot reconstruct on its own
    (`importance`, `category`'s raw string) -- see this module's own
    docstring for why this envelope, rather than broadening
    `Qualification` itself, is the fix. `legacy_category` is kept
    SEPARATE from `qualification.qualification_kind` on purpose: the
    two are never equated, never used to validate or override each
    other -- `qualification_kind` is this adapter's own internal,
    structural classification (used to pick a safe
    `NormalizedReference` shape and nothing else); `legacy_category` is
    the ORIGINAL string, preserved for its own sake, including a
    placeholder category's own identity (`"unresolved_requirement"`,
    `"alternative_requirement"`) exactly as it was.
    """

    qualification: Qualification
    legacy_importance: Importance
    legacy_category: str | None


def _qualification_kind_for_requirement(requirement: JobRequirement) -> QualificationKind:
    """Derive `QualificationKind` from STRUCTURAL facts only -- never
    from assuming `requirement.category` already speaks
    `QualificationKind`'s vocabulary (Stage 2A §1.10's own finding).
    `concept_id`/`alternative_concept_ids` being populated wins first,
    unconditionally, regardless of whatever `category` string
    accompanies it (a confirmed technical mention's `category` is a
    REGISTRY category like `"language"`, never `"specific_technology"`
    -- checking structure first, string second, is what makes this
    correct). This function's return value is used ONLY to pick
    `qualification_kind`; it never flows back into a reconstructed
    `category` (see `AdaptedQualification`/`job_requirement_from_adapted`).
    """
    if requirement.concept_id is not None or requirement.alternative_concept_ids:
        return QualificationKind.SPECIFIC_TECHNOLOGY
    if requirement.category == _EDUCATION_CATEGORY:
        return QualificationKind.EDUCATION
    if requirement.category == _EXPERIENCE_CATEGORY:
        return QualificationKind.EXPERIENCE
    if requirement.category in _NONTECHNICAL_CATEGORIES:
        return QualificationKind.NONTECHNICAL
    return QualificationKind.OTHER_LEGITIMATE


def qualification_from_job_requirement(requirement: JobRequirement) -> Qualification:
    """The Stage-1-only view: an EXISTING `JobRequirement` ->
    `Qualification`, with NO legacy-field envelope. Preserves
    `original_text`, `source_span`, `necessity`,
    `concept_id`/`alternative_concept_ids`, `github_observability`, and
    `parser_confidence` exactly. Does **not**, on its own, achieve full
    `JobRequirement` round-trip equality -- `importance` and the raw
    `category` string are not carried by `Qualification` at all; use
    `adapt_job_requirement()`/`job_requirement_from_adapted()` for a
    full-fidelity round trip. This function still exists because it is
    useful on its own (e.g. to inspect what Stage 1's model alone would
    say about an existing requirement), but it must never be presented
    as a complete round trip by itself.

    `applicability_condition`/`evidence_requirements` are always `None`
    -- `JobRequirement` has no corresponding field for either, so there
    is nothing to adapt FROM (not an information-loss point: the
    information never existed in the source type).

    `logical_composition` is `OR_ANY` when `alternative_concept_ids` is
    populated, `SINGLE` otherwise. `AND` and `MIXED_UNSUPPORTED` are
    NEVER produced here by construction -- both are facts about
    MULTIPLE sibling `JobRequirement` rows sharing one sentence rather
    than anything visible on a SINGLE `JobRequirement` in isolation --
    this adapter operates per-object and has no sibling-grouping logic,
    deliberately, per Stage 2A's own Phase 2 scope note.

    Raises `UnsupportedAdapterCase` (never fabricates a placeholder)
    when `requirement.source_span is None` -- `Qualification.source_span`
    is a required field with nothing safe to default it to.
    """
    if requirement.source_span is None:
        raise UnsupportedAdapterCase(
            reason="missing_source_span",
            detail=(
                "JobRequirement.source_span is None (optional on JobRequirement, "
                "e.g. a hand-constructed fixture) -- Qualification.source_span is "
                "required and has no safe default"
            ),
        )

    normalized_reference: NormalizedReference | None
    logical_composition: LogicalComposition
    if requirement.alternative_concept_ids:
        normalized_reference = NormalizedReference(alternative_concept_ids=requirement.alternative_concept_ids)
        logical_composition = LogicalComposition.OR_ANY
    elif requirement.concept_id is not None:
        normalized_reference = NormalizedReference(concept_id=requirement.concept_id)
        logical_composition = LogicalComposition.SINGLE
    else:
        normalized_reference = None
        logical_composition = LogicalComposition.SINGLE

    try:
        return Qualification(
            qualification_kind=_qualification_kind_for_requirement(requirement),
            source_text=requirement.original_text,
            source_span=requirement.source_span,
            necessity=requirement.necessity,
            applicability_condition=None,
            interpretation_certainty=requirement.parser_confidence,
            logical_composition=logical_composition,
            normalized_reference=normalized_reference,
            github_observability=requirement.github_observability,
            evidence_requirements=None,
        )
    except ValueError as exc:
        raise UnsupportedAdapterCase(reason="invalid_qualification_construction", detail=str(exc)) from exc


def adapt_job_requirement(requirement: JobRequirement) -> AdaptedQualification:
    """The FULL-FIDELITY Path A reverse mapping: an EXISTING
    `JobRequirement` -> `AdaptedQualification`. Wraps
    `qualification_from_job_requirement()`'s own `Qualification`
    together with `requirement.importance`/`requirement.category`,
    preserved verbatim, never transformed, never equated with anything
    `Qualification` itself carries. Raises `UnsupportedAdapterCase`
    under the identical condition `qualification_from_job_requirement()`
    does (missing `source_span`) -- this function adds no NEW failure
    mode of its own.
    """
    qualification = qualification_from_job_requirement(requirement)
    return AdaptedQualification(
        qualification=qualification,
        legacy_importance=requirement.importance,
        legacy_category=requirement.category,
    )


def job_requirement_from_adapted(adapted: AdaptedQualification) -> JobRequirement:
    """The full-fidelity reverse of `adapt_job_requirement()`. Calls the
    EXISTING, unmodified `project_qualification()` first -- every Stage
    1 safety rule (unknown necessity, unknown observability,
    `MIXED_UNSUPPORTED`, `UNINTERPRETABLE`, a material
    `applicability_condition`) still applies exactly as it does for any
    other caller of that function, unchanged by this module. If that
    projection is unsafe (which never occurs for a `Qualification` built
    from a real `JobRequirement` -- see this module's own docstring,
    and the Stage 2B harness's own measured 0 unsafe-projection count --
    but is not assumed impossible here), this function raises
    `UnsupportedAdapterCase` rather than fabricating a `JobRequirement`
    from nothing.

    Otherwise, `dataclasses.replace()` patches `importance`/`category`
    back onto the SAFELY projected `JobRequirement` with the EXACT
    original values `adapt_job_requirement()` captured -- never a
    derived value, never `qualification_kind.value`, never a value
    equated from `category`. `JobRequirement.__post_init__` re-runs
    through `replace()` exactly as it would for any other construction
    (both patched values were already valid on the original object, so
    this can never newly fail validation).
    """
    result = project_qualification(adapted.qualification)
    if result.job_requirement is None:
        raise UnsupportedAdapterCase(
            reason="unsafe_projection",
            detail=f"project_qualification() routed this Qualification to UnparsedClaim (unsafe_reason={result.unsafe_reason!r})",
        )
    return dataclasses.replace(
        result.job_requirement,
        importance=adapted.legacy_importance,
        category=adapted.legacy_category,
    )


def qualification_from_unparsed_claim(claim: UnparsedClaim) -> Qualification:
    """The Path A reverse mapping: an EXISTING `UnparsedClaim` ->
    `Qualification`. `UnparsedClaim` carries exactly two facts
    (`text`, `source_span`), both preserved exactly -- no envelope is
    needed here (contrast `JobRequirement`'s own two legacy scalars):
    `qualification_kind=UNINTERPRETABLE` is the honest declaration that
    nothing further is known. `necessity=None` is set because
    `UnparsedClaim` itself carries no necessity information to recover
    -- by the time `jobs/parsing/parser.py::_parse` constructs one,
    whatever necessity (if any) was resolved for that claim has already
    been discarded (see `_requirements_from_claim`'s own `necessity is
    None -> []` short-circuit). This is a pre-existing property of
    `UnparsedClaim`'s own shape, not something this function loses on
    its own.

    `project_qualification()` will route the result back to
    `UnparsedClaim` regardless of which safety rule fires first
    (`necessity_unknown` fires before `uninterpretable_kind` in
    `_unsafe_reason()`'s own checked order) -- the round trip is exact
    on the TWO fields `UnparsedClaim` actually has, which is the only
    claim this function makes.
    """
    try:
        return Qualification(
            qualification_kind=QualificationKind.UNINTERPRETABLE,
            source_text=claim.text,
            source_span=claim.source_span,
            necessity=None,
            applicability_condition=None,
            interpretation_certainty=None,
            logical_composition=LogicalComposition.SINGLE,
            normalized_reference=None,
            github_observability=None,
            evidence_requirements=None,
        )
    except ValueError as exc:
        raise UnsupportedAdapterCase(reason="invalid_qualification_construction", detail=str(exc)) from exc
