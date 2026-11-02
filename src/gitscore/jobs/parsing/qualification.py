"""Milestone 11-B Stage 1 -- internal structured qualification model.

**This module is NOT wired into the live parser.** Nothing in
`segment_description()`/`_requirements_from_claim()`/any other
production call path constructs a `Qualification` or calls
`project_qualification()` -- confirmed by construction, not merely
intended: this module imports only plain, behavior-free domain TYPES
(`JobRequirement`, `SourceSpan`, `UnparsedClaim`, the `jobs.types`
enums), never any detector/orchestration function
(`infer_necessity`, `find_concept_mentions`, `segment_description`,
`_requirements_from_claim`, ...), so there is no import-graph path by
which introducing this module could change what today's parser
actually does for any real job description. `JOB_DESCRIPTION_PARSER_VERSION`
is therefore UNCHANGED by this milestone -- a version bump signals a
change in observable parser BEHAVIOR (every prior milestone in this
series bumped it for exactly that reason), and this module changes
none.

See `docs/evaluation/MILESTONE_11_B_STRUCTURED_QUALIFICATION_MODEL.md`
for the full evaluation-first design review (Option C) this implements,
and that document's own §6.5 for why Stage 1 is scoped to ONLY this
model + its projection function -- no extraction-from-`Claim` bridge,
no `confidence.py` wiring, no public schema, matcher, scoring, API, or
frontend change of any kind.

**The two independent dimensions this model separates, per that
document's Phase 1 investigation (and the production-approval
message's own explicit requirement):**

1. `necessity: Necessity | None` -- the job's OWN stated requirement
   level. `None` means genuinely UNKNOWN/unresolved -- this is a
   distinct, explicit state, never conflated with low confidence in
   the parser's OWN reading. A `Qualification` can be `necessity=
   REQUIRED` with `interpretation_certainty=LOW` (the parser is SURE
   the posting says REQUIRED, but unsure about something else --
   e.g. a self-contradicting sentence) just as easily as it can be
   `necessity=None` with `interpretation_certainty=HIGH` (the parser
   is confident the text is genuinely silent on necessity, not merely
   unsure how to read it).
2. `interpretation_certainty: ParserConfidence | None` -- REUSES the
   EXISTING `gitscore.jobs.types.ParserConfidence` enum unchanged (see
   that enum's own docstring, and
   `docs/evaluation/MILESTONE_11_B_STRUCTURED_QUALIFICATION_MODEL.md`
   §0's own finding: it already exists, already populated in
   production, and already answers almost exactly this question for
   an unrelated Milestone 6B reason). `None` here means "not yet
   evaluated by anything" -- the SAME meaning `JobRequirement.parser_confidence`'s
   own docstring already gives `None`, never silently defaulted to a
   concrete confidence level that was never actually assessed
   (preserving uncertainty rather than fabricating certainty).

`applicability_condition` is a THIRD, separate dimension (never a
`Necessity` value) -- see `Qualification`'s own docstring below.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from gitscore.jobs.models import JobRequirement, SourceSpan
from gitscore.jobs.parsing.parser import UnparsedClaim
from gitscore.jobs.types import GithubObservability, Importance, Necessity, ParserConfidence


class QualificationKind(str, Enum):
    """What KIND of statement a claim is -- independent of whether
    GitHub evidence can speak to it at all (see
    `docs/evaluation/MILESTONE_11_B_STRUCTURED_QUALIFICATION_MODEL.md`
    §5: recognizing a kind is never the same act as having defensible
    evidence for it). Exactly the seven categories the mission named --
    no member added "to improve evaluation coverage" beyond that list.

    `UNINTERPRETABLE` answers "what kind of statement is this" with an
    honest "we don't know" -- a DIFFERENT question from
    `interpretation_certainty=LOW` on `Qualification` (below), which
    answers "we know the kind, but we're unsure about some OTHER
    dimension's value." The two are deliberately never conflated.
    """

    SPECIFIC_TECHNOLOGY = "specific_technology"
    TECHNICAL_COMPETENCY = "technical_competency"
    EDUCATION = "education"
    EXPERIENCE = "experience"
    NONTECHNICAL = "nontechnical"
    OTHER_LEGITIMATE = "other_legitimate"
    UNINTERPRETABLE = "uninterpretable"


class LogicalComposition(str, Enum):
    """How this claim's own content composes, if at all.

    `SINGLE`/`AND`/`OR_ANY` already exist IMPLICITLY in production today
    (separate `JobRequirement` rows for `AND`; `alternative_concept_ids`
    for `OR_ANY`) -- named here so a caller can branch on the VALUE
    directly rather than inferring it from field shape.
    `MIXED_UNSUPPORTED` is the one genuinely NEW value: an honest
    diagnostic for a structure (an AND of ORs, M10D's own Root Cause 6)
    this project has never been able to safely flatten -- never silently
    resolved to ONE of the simpler values, and never silently dropped.
    """

    SINGLE = "single"
    AND = "and"
    OR_ANY = "or_any"
    MIXED_UNSUPPORTED = "mixed_unsupported"


@dataclass(frozen=True)
class NormalizedReference:
    """What this claim resolves to, if anything -- a tagged union:
    EITHER a real registry concept (`concept_id`, mirroring
    `JobRequirement.concept_id` exactly, same validity rules enforced
    at projection time by `JobRequirement.__post_init__` itself, never
    duplicated here), OR an alternative GROUP of registry concepts
    (`alternative_concept_ids`, mirroring `JobRequirement.alternative_concept_ids`),
    OR a free, UNREGISTERED competency slug (`competency_tag` -- e.g.
    `"concurrency"`, `"circuit-theory"` -- deliberately never validated
    against the concept registry: no registry expansion, no detector,
    exactly the mission's own restriction). At most ONE of
    `concept_id`/`competency_tag` is set; `alternative_concept_ids` is
    mutually exclusive with `concept_id` (mirrors `JobRequirement`'s own
    invariant) but may coexist with neither in the illustrative case
    (`exhaustive=False`, no single `concept_id` because the list is
    explicitly incomplete).

    `exhaustive` (`True`/`False`/`None`) records whether the source text
    itself signals a COMPLETE enumeration ("one of the following:")
    versus an ILLUSTRATIVE example clause ("such as", "e.g.") versus
    undetermined (`None`). Not projected onto `JobRequirement` in Stage
    1 (no such field exists there) -- an explicit, documented
    information-loss point
    (`docs/evaluation/MILESTONE_11_B_STRUCTURED_QUALIFICATION_MODEL.md`
    §6.4), not a silent one.
    """

    concept_id: str | None = None
    alternative_concept_ids: tuple[str, ...] = ()
    competency_tag: str | None = None
    exhaustive: bool | None = None

    def __post_init__(self) -> None:
        if self.concept_id is not None and self.alternative_concept_ids:
            raise ValueError(
                "NormalizedReference cannot set both concept_id and alternative_concept_ids "
                "-- a reference is either ONE concept or an alternative GROUP, never both"
            )
        if self.concept_id is not None and self.competency_tag is not None:
            raise ValueError(
                "NormalizedReference cannot set both concept_id and competency_tag -- "
                "a reference naming a registered concept is never ALSO an unregistered competency slug"
            )
        if self.alternative_concept_ids and self.competency_tag is not None:
            raise ValueError(
                "NormalizedReference cannot set both alternative_concept_ids and competency_tag"
            )


@dataclass(frozen=True)
class Qualification:
    """One semantically-interpreted applicant qualification claim --
    INTERNAL ONLY (see this module's own docstring for why nothing in
    the live parser constructs one yet). Mirrors
    `jobs.parsing.segmentation.Claim`'s own "exact text and offsets into
    the ORIGINAL description" discipline for `source_text`/`source_span`
    -- never reconstructed or approximated.

    Every dimension below is INDEPENDENT -- see this module's own
    docstring and
    `docs/evaluation/MILESTONE_11_B_STRUCTURED_QUALIFICATION_MODEL.md`
    §1 for the full investigation each one answers. In particular:
    `necessity=None` (genuinely unknown) is NEVER the same fact as
    `interpretation_certainty=LOW` (uncertain about some OTHER
    dimension) -- a caller must check both independently, never infer
    one from the other.

    `applicability_condition` -- the verbatim conditional clause
    ("unless you can demonstrate equivalent practical experience"), or
    `None` for an unconditional claim. A SEPARATE dimension from
    `necessity`, never a `Necessity` enum value: `necessity` always
    carries the claim's PRIMARY, stated reading; the condition is
    additional context a consumer may act on or safely ignore, falling
    back to that primary reading. `JobRequirement` has no field to hold
    this (Stage 1 adds none) -- see `project_qualification()`'s own
    safety rule this implies.
    """

    qualification_kind: QualificationKind
    source_text: str
    source_span: SourceSpan
    necessity: Necessity | None = None
    applicability_condition: str | None = None
    interpretation_certainty: ParserConfidence | None = None
    logical_composition: LogicalComposition = LogicalComposition.SINGLE
    normalized_reference: NormalizedReference | None = None
    github_observability: GithubObservability | None = None
    evidence_requirements: str | None = None

    def __post_init__(self) -> None:
        if not self.source_text.strip():
            raise ValueError("Qualification.source_text must not be empty/whitespace-only")
        if self.applicability_condition is not None and not self.applicability_condition.strip():
            raise ValueError(
                "Qualification.applicability_condition must be None, not an empty/whitespace-only string "
                "-- use None for 'no condition,' never a blank string"
            )


@dataclass(frozen=True)
class ProjectionResult:
    """The outcome of `project_qualification()` -- EXACTLY one of
    `job_requirement`/`unparsed_claim` is populated, never both, never
    neither (enforced by `__post_init__`, not merely by convention).
    `unsafe_reason` is `None` iff `job_requirement` is populated --
    a human/test-readable string naming WHY a safe projection was not
    possible, never silently absent when a claim was routed to
    `unparsed_claim` (see `project_qualification()`'s own docstring for
    the full, named list of reasons).
    """

    job_requirement: JobRequirement | None = None
    unparsed_claim: UnparsedClaim | None = None
    unsafe_reason: str | None = None

    def __post_init__(self) -> None:
        populated = [x is not None for x in (self.job_requirement, self.unparsed_claim)]
        if sum(populated) != 1:
            raise ValueError(
                "ProjectionResult must populate EXACTLY ONE of job_requirement/unparsed_claim, "
                f"got job_requirement={self.job_requirement!r} unparsed_claim={self.unparsed_claim!r}"
            )
        if (self.unparsed_claim is not None) != (self.unsafe_reason is not None):
            raise ValueError(
                "ProjectionResult.unsafe_reason must be set iff unparsed_claim is populated "
                "(and must be None iff job_requirement is populated)"
            )


# Milestone 11-B Stage 1 -- `JobRequirement.importance` has no `None`/
# "not yet computed" state (unlike `parser_confidence`); `Qualification`
# deliberately carries no `importance` field at all (the mission's own
# Phase 1 dimension list never named it -- it is `jobs.types.Importance`'s
# own, separate, pre-existing axis, computed today by
# `jobs.parsing.importance.infer_importance()`, a detector this
# standalone module never calls). Projecting to `JobRequirement`
# therefore needs SOME value; `MEDIUM` is used as an explicit,
# documented, NEUTRAL placeholder -- never `HIGH` or `LOW` (which would
# claim a judgment this module never made). A future stage that wires
# real importance inference in would replace this constant with a real
# value, not change this module's own contract.
_STAGE_1_PLACEHOLDER_IMPORTANCE = Importance.MEDIUM


def _unsafe_reason(qualification: Qualification) -> str | None:
    """Every reason `project_qualification()` routes a `Qualification`
    to `UnparsedClaim` instead of `JobRequirement` -- checked in this
    order, the first match wins (order does not change the OUTCOME,
    since these are independent gates, only which single reason string
    is reported when more than one would apply).
    """
    if qualification.necessity is None:
        return "necessity_unknown"
    if qualification.github_observability is None:
        return "observability_unknown"
    if qualification.logical_composition is LogicalComposition.MIXED_UNSUPPORTED:
        return "mixed_unsupported_logical_structure"
    if qualification.qualification_kind is QualificationKind.UNINTERPRETABLE:
        return "uninterpretable_kind"
    if qualification.applicability_condition is not None:
        return "material_applicability_condition_not_representable_on_job_requirement"
    return None


def project_qualification(qualification: Qualification) -> ProjectionResult:
    """The ONE, pure, deterministic function this milestone adds that
    turns a `Qualification` into one of the TWO destinations that
    already exist in production today -- never a third. Safety rules,
    each independently checked by `_unsafe_reason()` above, in order of
    the mission's own explicit requirements:

    1. **Unknown necessity is never silently coerced** to REQUIRED or
       PREFERRED -- `necessity is None` always routes to `UnparsedClaim`
       (`unsafe_reason="necessity_unknown"`).
    2. **Unknown observability is never silently coerced** either, for
       the identical reason (`JobRequirement.github_observability` is
       non-nullable; inventing a value here would be exactly the same
       kind of fabrication unknown-necessity-coercion would be).
    3. **A `MIXED_UNSUPPORTED` logical structure is never falsely
       simplified** -- routed to `UnparsedClaim`
       (`unsafe_reason="mixed_unsupported_logical_structure"`), never
       flattened into a `SINGLE`/`AND`/`OR_ANY` shape that would
       misrepresent the source text's own logical structure.
    4. **A material applicability condition is never silently lost**
       -- `JobRequirement` has no field to hold
       `applicability_condition` at all, so a `Qualification` that
       carries one is NOT safely projectable to it (losing the
       condition would be exactly the "losing material semantics"
       this function must never do); routed to `UnparsedClaim` instead,
       whose `text` still carries the full original sentence --
       including the condition -- verbatim.
    5. **`UNINTERPRETABLE` is never forced into a scored row** --
       routed to `UnparsedClaim`.

    In every unsafe case, the `UnparsedClaim` still carries the
    qualification's own `source_text`/`source_span` exactly --
    `project_qualification()` never drops a `Qualification` with
    neither output populated (enforced by `ProjectionResult.__post_init__`
    itself, not merely by this function's own care).

    A SAFE projection additionally validates through
    `JobRequirement.__post_init__`'s own existing invariants (a real
    `concept_id` shape, a well-formed `alternative_concept_ids` group,
    ...) unchanged -- if those reject the constructed values (e.g. a
    malformed `NormalizedReference` nobody caught earlier), this
    function catches that `ValueError` and falls back to `UnparsedClaim`
    (`unsafe_reason="invalid_normalized_reference"`) rather than letting
    an unrelated caller's bad input crash the whole projection.
    """
    reason = _unsafe_reason(qualification)
    if reason is not None:
        return ProjectionResult(
            unparsed_claim=UnparsedClaim(text=qualification.source_text, source_span=qualification.source_span),
            unsafe_reason=reason,
        )

    ref = qualification.normalized_reference
    concept_id = ref.concept_id if ref is not None else None
    alternative_concept_ids = ref.alternative_concept_ids if ref is not None else ()

    try:
        requirement = JobRequirement(
            original_text=qualification.source_text,
            necessity=qualification.necessity,
            importance=_STAGE_1_PLACEHOLDER_IMPORTANCE,
            github_observability=qualification.github_observability,
            concept_id=concept_id,
            alternative_concept_ids=alternative_concept_ids,
            category=qualification.qualification_kind.value,
            parser_confidence=qualification.interpretation_certainty,
            source_span=qualification.source_span,
        )
    except ValueError:
        return ProjectionResult(
            unparsed_claim=UnparsedClaim(text=qualification.source_text, source_span=qualification.source_span),
            unsafe_reason="invalid_normalized_reference",
        )

    return ProjectionResult(job_requirement=requirement)
