"""Milestone 11-G11 -- structured semantic-extraction feasibility prototype.

Evaluation-only, exactly like `m11g10_competency_concept_model.py` before it.
Nothing in `src/gitscore` imports this module (confirmed by
`tests/test_m11g11_structured_extraction_feasibility.py`, not merely
intended). No real LLM call, external model API request, or production
change is made anywhere in this file -- every "extractor output" used by
this module's tests is a manually authored `CandidateQualification` literal,
never a model response.

This module proposes two things, per
`docs/evaluation/MILESTONE_11_G11_STRUCTURED_EXTRACTION_FEASIBILITY.md`'s
Phase 2/3 design:

1. A structured-output CONTRACT (`CandidateQualification` +
   `ProposedConceptReference`) a future semantic extractor could be asked
   to return.
2. A DETERMINISTIC VALIDATOR (`validate_candidate()`) that treats every
   field of that contract as untrusted candidate data -- never as an
   instruction, never as ground truth. The validator only ever compares
   plain strings against the original job-description text; it never
   evaluates, formats, or executes any extractor-supplied field, so a
   prompt-injection string inside a job posting cannot change the
   validator's control flow or leak state between candidates. It CAN still
   change a decision at the data level: the necessity check accepts any
   local quote containing a bounded keyword, so an injected or negated
   sentence ("you must ...", "is not required") is wrongly accepted as
   necessity evidence. This is an unresolved safety issue, demonstrated
   (not fixed) by the prompt-injection adversarial test.

   Passing validation establishes only that quotes are verbatim and local
   and that concept refs exist in the G10 graph with the checked relation;
   it does NOT establish that the extractor's claims are semantically
   correct.

Reuses, rather than duplicates: `gitscore.jobs.models.SourceSpan`,
`gitscore.jobs.parsing.qualification.{LogicalComposition, QualificationKind}`,
`gitscore.jobs.types.GithubObservability`, and the offline
`m11g10_competency_concept_model` graph/`ConceptRef`/`ConceptStatus`/
`ConceptRelationType` for ontology grounding. No new concept vocabulary, no
registry expansion, no matcher/scoring change.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT / "src", _REPO_ROOT / "scripts" / "evaluation_lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from gitscore.jobs.models import SourceSpan  # noqa: E402
from gitscore.jobs.parsing.qualification import LogicalComposition, QualificationKind  # noqa: E402

import m11g10_competency_concept_model as g10  # noqa: E402

EXTRACTION_SCHEMA_VERSION = 1
"""Independent of `g10.COMPETENCY_CONCEPT_MODEL_VERSION` (1),
`JOB_REQUIREMENT_SCHEMA_VERSION` (2), and `CONCEPT_REGISTRY_VERSION` (4) --
a fifth, offline-only versioning axis for this milestone's own candidate
contract. Bump on any shape change to `CandidateQualification`/
`ProposedConceptReference`; `validate_candidate()` does not currently check
this against anything (there is no persisted artifact yet to compare
against, unlike G10's `deserialize_graph()`), but a future on-disk
candidate-batch format should hard-fail on mismatch the same way."""

LOCAL_EVIDENCE_WINDOW_CHARS = 160
"""How far (in characters) a supporting-evidence quote may sit from the
claimed span and still count as "local." Blocks evidence drawn from a
distant, unrelated part of the document (Phase 3: "reject unrelated quoted
text and cross-span combinations") while tolerating evidence that sits in
the same sentence/bullet as the span but just outside it."""


# ---------------------------------------------------------------------------
# Phase 2 -- the candidate contract
# ---------------------------------------------------------------------------


class ApplicantClassification(str, Enum):
    """Item 3 of the Phase 2 contract. `AMBIGUOUS` is a real, distinct
    outcome -- the validator downgrades to it rather than guessing between
    the other two when local evidence does not clearly support one."""

    QUALIFICATION = "qualification"
    RESPONSIBILITY_OR_NARRATIVE = "responsibility_or_narrative"
    AMBIGUOUS = "ambiguous"


class ExtractedNecessity(str, Enum):
    """Three states, unlike production `jobs.types.Necessity`'s deliberate
    two (`REQUIRED`/`PREFERRED` only, see that enum's own docstring).  This
    is CANDIDATE, pre-validation output, where "the extractor could not
    tell" is itself a fact the contract must be able to carry.  `UNKNOWN`
    is never projected onto a `Qualification`/`JobRequirement` by this
    module -- it exists purely on this untrusted candidate side, exactly
    mirroring why `Qualification.necessity` is `Necessity | None` rather
    than defaulting to a guess.
    """

    REQUIRED = "required"
    PREFERRED = "preferred"
    UNKNOWN = "unknown"


_NECESSITY_KEYWORDS: dict[ExtractedNecessity, tuple[str, ...]] = {
    ExtractedNecessity.REQUIRED: (
        "required", "must have", "must", "minimum qualification", "minimum qualifications", "mandatory",
    ),
    ExtractedNecessity.PREFERRED: (
        "preferred", "nice to have", "a plus", "bonus", "ideally",
    ),
}


@dataclass(frozen=True)
class ProposedConceptReference:
    """What the extractor proposes a span resolves to -- a tagged union
    mirroring `NormalizedReference`/`g10.ConceptRef`'s own XOR discipline,
    plus an explicit `unresolved_term` slot (Phase 2 item 8: "unresolved/
    out-of-ontology concepts" must stay VISIBLE, never silently dropped or
    silently force-mapped onto the nearest known concept).

    `candidate_alternative_refs` is the extractor's claimed OR-group (item
    9's grouping, concept side) -- `validate_candidate()` independently
    verifies that every pair in this group is an authored EQUIVALENT edge
    in the G10 graph before treating the group as truly interchangeable
    (see `_resolve_concept()`); a `RELATED_ONLY` pair (Docker/Kubernetes,
    AWS/Azure) is never accepted as an alternative group.
    """

    candidate_ref: "g10.ConceptRef | None" = None
    candidate_alternative_refs: "tuple[g10.ConceptRef, ...]" = ()
    unresolved_term: str | None = None
    exhaustive: bool | None = None

    def __post_init__(self) -> None:
        populated = [
            self.candidate_ref is not None,
            bool(self.candidate_alternative_refs),
            self.unresolved_term is not None,
        ]
        if sum(populated) > 1:
            raise ValueError(
                "ProposedConceptReference must set AT MOST ONE of "
                "candidate_ref/candidate_alternative_refs/unresolved_term"
            )


@dataclass(frozen=True)
class CandidateQualification:
    """ONE untrusted candidate qualification, exactly as a future
    structured extractor would be asked to return it. Every field here is
    DATA, never code or an instruction -- `validate_candidate()` never
    evaluates, formats, or executes any string field; it only compares them
    as plain text against the original `job_text`.

    Covers all 11 items the Phase 2 brief named: (1)/(2) `source_text` +
    `source_span`; (3) `applicant_classification`; (4)
    `classification_evidence`; (5) `proposed_necessity` +
    `necessity_evidence`; (6) `qualification_kind` (`is_technical` derives
    from it, no second duplicate enum); (7) `proposed_concept`; (8)
    `proposed_concept.unresolved_term`; (9) `logical_composition` +
    `applicability_condition`; (10) `ambiguity_reason` /
    `extractor_decline_reason`; (11) `schema_version`.
    """

    source_text: str
    source_span: SourceSpan
    applicant_classification: ApplicantClassification
    classification_evidence: str
    proposed_necessity: ExtractedNecessity
    qualification_kind: QualificationKind
    proposed_concept: ProposedConceptReference
    necessity_evidence: str | None = None
    logical_composition: LogicalComposition = LogicalComposition.SINGLE
    applicability_condition: str | None = None
    ambiguity_reason: str | None = None
    extractor_decline_reason: str | None = None
    schema_version: int = EXTRACTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.source_text.strip():
            raise ValueError("CandidateQualification.source_text must not be empty/whitespace-only")
        if not self.classification_evidence.strip():
            raise ValueError("CandidateQualification.classification_evidence must not be empty/whitespace-only")
        if self.schema_version != EXTRACTION_SCHEMA_VERSION:
            raise ValueError(
                f"CandidateQualification.schema_version {self.schema_version!r} does not match "
                f"EXTRACTION_SCHEMA_VERSION {EXTRACTION_SCHEMA_VERSION!r}"
            )

    @property
    def is_technical(self) -> bool:
        """Item 6's technical/nontechnical split, derived from the EXISTING
        `QualificationKind` rather than a second, duplicate enum."""
        return self.qualification_kind in (
            QualificationKind.SPECIFIC_TECHNOLOGY,
            QualificationKind.TECHNICAL_COMPETENCY,
        )


# ---------------------------------------------------------------------------
# Phase 3 -- the deterministic validator
# ---------------------------------------------------------------------------


class ConceptResolutionStatus(str, Enum):
    RESOLVED_ACTIVE = "resolved_active"
    RESOLVED_PROVISIONAL = "resolved_provisional"
    RESOLVED_REJECTED = "resolved_rejected"
    UNRESOLVED_OUT_OF_ONTOLOGY = "unresolved_out_of_ontology"
    AMBIGUOUS = "ambiguous"
    DECLINED_NON_EQUIVALENT_GROUP = "declined_non_equivalent_group"
    DECLINED_NO_PROPOSAL = "declined_no_proposal"


@dataclass(frozen=True)
class ConceptResolution:
    status: ConceptResolutionStatus
    resolved_ref: "g10.ConceptRef | None" = None
    note: str = ""


@dataclass(frozen=True)
class ValidationResult:
    """The validator's verdict on ONE candidate. Deliberately keeps every
    dimension separate (Phase 3: "do not collapse genuine qualifications,
    recognized concepts, GitHub assessability and proven repository
    evidence into a single status") -- a caller reads each field
    independently, never infers one from another.

    `accepted_for_review` is the ONE boolean gate, and it answers only ONE
    question: is the span genuine and is the (post-validation)
    classification `QUALIFICATION`. It is never a claim that necessity,
    concept, or grouping were resolved with full confidence -- a result can
    be `accepted_for_review=True` with `necessity=UNKNOWN`, an unresolved
    concept, and a downgraded grouping, all at once.
    """

    candidate: CandidateQualification
    span_valid: bool
    span_rejection_reason: str | None
    classification: ApplicantClassification
    classification_downgrade_reason: str | None
    necessity: ExtractedNecessity
    necessity_downgrade_reason: str | None
    concept_resolution: ConceptResolution
    grouping: LogicalComposition
    grouping_downgrade_reason: str | None
    decline_reasons: tuple[str, ...]
    accepted_for_review: bool


def _find_local_offset(job_text: str, quote: str, span: SourceSpan) -> int | None:
    """The character offset of `quote` in `job_text`, restricted to an
    occurrence within `LOCAL_EVIDENCE_WINDOW_CHARS` of `span` -- or `None`
    if no such occurrence exists. This is the ONE primitive that blocks
    "cross-span" evidence fabrication: a quote that is genuinely present
    somewhere in `job_text` but nowhere near the claimed span does not
    count."""
    if not quote:
        return None
    start_search = max(0, span.start - LOCAL_EVIDENCE_WINDOW_CHARS)
    end_search = min(len(job_text), span.end + LOCAL_EVIDENCE_WINDOW_CHARS)
    window = job_text[start_search:end_search]
    local_idx = window.find(quote)
    if local_idx == -1:
        return None
    return start_search + local_idx


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(k in lowered for k in keywords)


_RESPONSIBILITY_MARKERS = (
    "you will", "responsibilities include", "the role involves", "day-to-day",
    "in this role, you", "duties include",
)
_APPLICANT_QUALIFICATION_MARKERS = (
    "you have", "you must", "you are", "the ideal candidate", "candidates must",
    "we are looking for someone who", "applicants must", "required skills",
)
_COMPANY_NARRATIVE_MARKERS = (
    "our company", "we are a", "founded in", "we have been", "about us",
)


def _resolve_concept(proposal: ProposedConceptReference, graph: "g10.CompetencyConceptGraph") -> ConceptResolution:
    if proposal.unresolved_term is not None:
        return ConceptResolution(ConceptResolutionStatus.UNRESOLVED_OUT_OF_ONTOLOGY, note=proposal.unresolved_term)

    if proposal.candidate_alternative_refs:
        refs = proposal.candidate_alternative_refs
        # An alternative group needs at least two DISTINCT members. A
        # one-member or duplicate-member "group" is malformed untrusted
        # input: decline it rather than resolving it (a lone member would
        # otherwise bypass the per-node status check below) or crashing
        # (G10's lookup_relation() raises on identical refs).
        if len({r.key for r in refs}) != len(refs) or len(refs) < 2:
            return ConceptResolution(
                ConceptResolutionStatus.DECLINED_NON_EQUIVALENT_GROUP,
                note="alternative group must have at least two distinct members",
            )
        nodes = [graph.node(r) for r in refs]
        if any(n is None for n in nodes):
            return ConceptResolution(
                ConceptResolutionStatus.UNRESOLVED_OUT_OF_ONTOLOGY,
                note="one or more alternative-group members not found in the concept graph",
            )
        # Every pair in a proposed alternative group must be an explicit,
        # authored EQUIVALENT edge -- RELATED_ONLY (or unknown/ambiguous) is
        # never enough to treat two concepts as interchangeable alternatives
        # (the Docker/Kubernetes, AWS/Azure adversarial safety case).
        for i in range(len(refs)):
            for j in range(i + 1, len(refs)):
                lookup = graph.lookup_relation(refs[i], refs[j])
                if lookup.status == "ambiguous":
                    return ConceptResolution(ConceptResolutionStatus.AMBIGUOUS, note=lookup.note)
                if not (lookup.status == "resolved" and lookup.relation == g10.ConceptRelationType.EQUIVALENT):
                    rel_note = lookup.relation.value if lookup.relation else lookup.status
                    return ConceptResolution(
                        ConceptResolutionStatus.DECLINED_NON_EQUIVALENT_GROUP,
                        note=f"{refs[i].key} / {refs[j].key} relation is {rel_note!r}, not EQUIVALENT",
                    )
        # An EQUIVALENT edge says nothing about review status: the group
        # takes its WORST member status, so a REJECTED or PROVISIONAL
        # concept can never be promoted to ACTIVE by being grouped.
        statuses = {n.status for n in nodes}
        if g10.ConceptStatus.REJECTED in statuses:
            return ConceptResolution(
                ConceptResolutionStatus.RESOLVED_REJECTED, note="equivalent alternative group with a REJECTED member"
            )
        if g10.ConceptStatus.PROVISIONAL in statuses:
            return ConceptResolution(
                ConceptResolutionStatus.RESOLVED_PROVISIONAL,
                note="equivalent alternative group with a PROVISIONAL member",
            )
        return ConceptResolution(ConceptResolutionStatus.RESOLVED_ACTIVE, note="equivalent alternative group")

    if proposal.candidate_ref is None:
        return ConceptResolution(ConceptResolutionStatus.DECLINED_NO_PROPOSAL)

    node = graph.node(proposal.candidate_ref)
    if node is None:
        return ConceptResolution(ConceptResolutionStatus.UNRESOLVED_OUT_OF_ONTOLOGY, note=proposal.candidate_ref.key)
    status_map = {
        g10.ConceptStatus.ACTIVE: ConceptResolutionStatus.RESOLVED_ACTIVE,
        g10.ConceptStatus.PROVISIONAL: ConceptResolutionStatus.RESOLVED_PROVISIONAL,
        g10.ConceptStatus.REJECTED: ConceptResolutionStatus.RESOLVED_REJECTED,
    }
    return ConceptResolution(status_map[node.status], resolved_ref=proposal.candidate_ref)


def validate_candidate(
    candidate: CandidateQualification,
    job_text: str,
    graph: "g10.CompetencyConceptGraph",
) -> ValidationResult:
    """Validates ONE candidate against the original `job_text` and the
    offline G10 ontology. Pure and deterministic: same inputs, same output,
    every time; never calls an external service, never evaluates any
    extractor-supplied string as code.
    """
    decline_reasons: list[str] = []

    # 1/2 -- span genuineness: the one check that, if it fails, makes every
    # other field meaningless (an extractor that can fabricate a span can
    # fabricate anything "about" it).
    s, e = candidate.source_span.start, candidate.source_span.end
    span_valid = True
    span_rejection_reason: str | None = None
    if not (0 <= s < e <= len(job_text)):
        span_valid = False
        span_rejection_reason = "span_out_of_bounds"
    elif job_text[s:e] != candidate.source_text:
        span_valid = False
        span_rejection_reason = "span_text_mismatch"

    if not span_valid:
        return ValidationResult(
            candidate=candidate,
            span_valid=False,
            span_rejection_reason=span_rejection_reason,
            classification=ApplicantClassification.AMBIGUOUS,
            classification_downgrade_reason="span_invalid",
            necessity=ExtractedNecessity.UNKNOWN,
            necessity_downgrade_reason="span_invalid",
            concept_resolution=ConceptResolution(ConceptResolutionStatus.DECLINED_NO_PROPOSAL, note="span_invalid"),
            grouping=LogicalComposition.MIXED_UNSUPPORTED,
            grouping_downgrade_reason="span_invalid",
            decline_reasons=(span_rejection_reason,),
            accepted_for_review=False,
        )

    # 3/4 -- classification evidence must be a genuine, LOCAL quote; a
    # classification whose own evidence reads as responsibility/company
    # narrative language (and not also applicant-qualification language) is
    # downgraded, never trusted at face value.
    classification = candidate.applicant_classification
    classification_downgrade_reason: str | None = None
    evidence_offset = _find_local_offset(job_text, candidate.classification_evidence, candidate.source_span)
    if evidence_offset is None:
        classification = ApplicantClassification.AMBIGUOUS
        classification_downgrade_reason = "classification_evidence_not_local_or_not_found"
    elif classification == ApplicantClassification.QUALIFICATION:
        ev = candidate.classification_evidence
        has_applicant_marker = _contains_any(ev, _APPLICANT_QUALIFICATION_MARKERS)
        if _contains_any(ev, _RESPONSIBILITY_MARKERS) and not has_applicant_marker:
            classification = ApplicantClassification.RESPONSIBILITY_OR_NARRATIVE
            classification_downgrade_reason = "responsibility_language_in_evidence"
        elif _contains_any(ev, _COMPANY_NARRATIVE_MARKERS) and not has_applicant_marker:
            classification = ApplicantClassification.RESPONSIBILITY_OR_NARRATIVE
            classification_downgrade_reason = "company_narrative_in_evidence"
    if classification_downgrade_reason:
        decline_reasons.append(classification_downgrade_reason)

    # 5 -- necessity must be supported by a genuine, local, keyword-bearing
    # quote; unsupported REQUIRED/PREFERRED claims are downgraded to
    # UNKNOWN, never trusted at face value.
    necessity = candidate.proposed_necessity
    necessity_downgrade_reason: str | None = None
    if necessity != ExtractedNecessity.UNKNOWN:
        ev = candidate.necessity_evidence
        ev_offset = _find_local_offset(job_text, ev, candidate.source_span) if ev else None
        if ev_offset is None:
            necessity = ExtractedNecessity.UNKNOWN
            necessity_downgrade_reason = "necessity_evidence_not_local_or_missing"
        elif not _contains_any(ev, _NECESSITY_KEYWORDS[necessity]):
            necessity = ExtractedNecessity.UNKNOWN
            necessity_downgrade_reason = "necessity_evidence_lacks_supporting_keyword"
        if necessity_downgrade_reason:
            decline_reasons.append(necessity_downgrade_reason)

    # 6/7/8 -- concept resolution against the offline G10 ontology;
    # out-of-ontology stays VISIBLE, REJECTED-status nodes resolve but are
    # never treated as ACTIVE, non-equivalent alternative groups are
    # declined rather than accepted as interchangeable.
    concept_resolution = _resolve_concept(candidate.proposed_concept, graph)
    if concept_resolution.status != ConceptResolutionStatus.RESOLVED_ACTIVE:
        decline_reasons.append(concept_resolution.status.value)

    # 9 -- AND/OR grouping must be textually evidenced within the span
    # itself, never trusted from the extractor's bare label.
    grouping = candidate.logical_composition
    grouping_downgrade_reason: str | None = None
    text_lower = candidate.source_text.lower()
    if grouping == LogicalComposition.OR_ANY:
        if " or " not in text_lower and "either" not in text_lower:
            grouping = LogicalComposition.MIXED_UNSUPPORTED
            grouping_downgrade_reason = "or_grouping_not_textually_evidenced"
        elif len(candidate.proposed_concept.candidate_alternative_refs) < 2:
            grouping = LogicalComposition.MIXED_UNSUPPORTED
            grouping_downgrade_reason = "or_grouping_missing_alternative_concepts"
    elif grouping == LogicalComposition.AND:
        if " and " not in text_lower and "as well as" not in text_lower:
            grouping = LogicalComposition.MIXED_UNSUPPORTED
            grouping_downgrade_reason = "and_grouping_not_textually_evidenced"
    if grouping_downgrade_reason:
        decline_reasons.append(grouping_downgrade_reason)

    accepted_for_review = classification == ApplicantClassification.QUALIFICATION

    return ValidationResult(
        candidate=candidate,
        span_valid=True,
        span_rejection_reason=None,
        classification=classification,
        classification_downgrade_reason=classification_downgrade_reason,
        necessity=necessity,
        necessity_downgrade_reason=necessity_downgrade_reason,
        concept_resolution=concept_resolution,
        grouping=grouping,
        grouping_downgrade_reason=grouping_downgrade_reason,
        decline_reasons=tuple(decline_reasons),
        accepted_for_review=accepted_for_review,
    )


def detect_overlapping_conflicts(
    results: "tuple[ValidationResult, ...]",
) -> "tuple[tuple[ValidationResult, ValidationResult], ...]":
    """Finds pairs of accepted-for-review results whose spans overlap but
    whose (validated, post-downgrade) necessity disagrees -- flags the
    conflict for human review rather than silently merging or silently
    preferring one (Phase 3: "deduplicate overlapping extraction results
    without destroying provenance", "reject inconsistent or contradictory
    claims"). Both original results are preserved in the returned pair;
    this function never discards either. A pair where either side's
    necessity is `UNKNOWN` is not flagged as contradictory -- `UNKNOWN`
    carries no claim to disagree with.
    """
    conflicts: list[tuple[ValidationResult, ValidationResult]] = []
    accepted = [r for r in results if r.accepted_for_review]
    for i in range(len(accepted)):
        for j in range(i + 1, len(accepted)):
            a, b = accepted[i], accepted[j]
            sa, ea = a.candidate.source_span.start, a.candidate.source_span.end
            sb, eb = b.candidate.source_span.start, b.candidate.source_span.end
            overlaps = sa < eb and sb < ea
            disagree = a.necessity != b.necessity and ExtractedNecessity.UNKNOWN not in (a.necessity, b.necessity)
            if overlaps and disagree:
                conflicts.append((a, b))
    return tuple(conflicts)


# ---------------------------------------------------------------------------
# Phase 6 -- future empirical comparison protocol (specification, not code
# that runs an experiment: no extractor is called here, this only names the
# metrics a SEPARATELY AUTHORIZED future experiment must report).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FutureExperimentMetric:
    name: str
    definition: str
    safety_threshold: str


FUTURE_EXPERIMENT_METRICS: tuple[FutureExperimentMetric, ...] = (
    FutureExperimentMetric(
        "qualification_level_precision_recall",
        "Precision/recall of whole-qualification extraction against a frozen holdout gold set, "
        "using ONE consistent denominator convention (per-control, named explicitly -- "
        "see G8's own M11-F/G5 reconciliation for why this matters).",
        "Recall improvement over the deterministic v2/v3 baseline must be statistically "
        "distinguishable from noise on an independent holdout, not merely non-zero on the dev set.",
    ),
    FutureExperimentMetric(
        "competency_level_precision_recall",
        "Precision/recall of individual competency-concept assignment, scored only over "
        "accepted_for_review candidates.",
        "No regression versus the deterministic extractor's own competency-level precision.",
    ),
    FutureExperimentMetric(
        "false_applicant_requirements_rate",
        "Rate at which a RESPONSIBILITY_OR_NARRATIVE or company-narrative sentence is extracted "
        "and validated as an accepted applicant QUALIFICATION.",
        "Must be at or below the rate already observed for the deterministic parser on the same holdout.",
    ),
    FutureExperimentMetric(
        "necessity_correctness",
        "Agreement between validated necessity (REQUIRED/PREFERRED/UNKNOWN) and gold necessity.",
        "No increase in REQUIRED-labeled-as-PREFERRED or PREFERRED-labeled-as-REQUIRED confusions "
        "versus the deterministic baseline.",
    ),
    FutureExperimentMetric(
        "concept_correctness",
        "Rate at which a resolved concept (ACTIVE/PROVISIONAL) is the semantically correct concept, "
        "not merely a well-formed one.",
        "Must be independently annotated; validator's RESOLVED_ACTIVE status is not itself proof of "
        "correctness (see 'Unsolved semantic validation problems' in the milestone doc).",
    ),
    FutureExperimentMetric(
        "grouping_and_condition_correctness",
        "Agreement between validated AND/OR/conditional structure and gold logical structure.",
        "MIXED_UNSUPPORTED downgrade rate must not exceed the rate of genuinely mixed structures "
        "in the gold set (i.e. the validator is not discarding resolvable structure).",
    ),
    FutureExperimentMetric(
        "source_provenance_correctness",
        "Rate at which span_valid=True candidates have source_text that is both verbatim and the "
        "MINIMAL sentence/clause actually making the claim (not an over-wide or under-wide span).",
        "No regression versus the deterministic parser's own span discipline.",
    ),
    FutureExperimentMetric(
        "validator_rejection_rate",
        "Fraction of raw extractor candidates rejected/downgraded at each validator stage "
        "(span, classification, necessity, concept, grouping), broken out separately.",
        "Reported for transparency; not itself a pass/fail threshold, but a sustained majority "
        "rejection rate would itself be a Phase 7 'stop' signal.",
    ),
    FutureExperimentMetric(
        "github_assessability_eligibility",
        "Fraction of accepted candidates whose resolved concept has STRONGLY_OBSERVABLE or "
        "PARTIALLY_OBSERVABLE GitHub observability, i.e. would actually change a matcher/score "
        "denominator if wired in.",
        "Must be computed and reported even though this milestone wires nothing into the matcher.",
    ),
    FutureExperimentMetric(
        "latency_and_operational_cost",
        "Wall-clock latency and per-posting cost, using the explicit assumptions from Phase 4 "
        "(never an invented measured price).",
        "Must be compared against the deterministic parser's own near-zero marginal cost/latency.",
    ),
)
