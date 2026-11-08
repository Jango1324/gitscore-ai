"""Milestone 11-G12 -- structured-extraction validator safety hardening.

Evaluation-only and offline, exactly like the G10/G11 modules it builds
on. Nothing in `src/gitscore` imports this module; no LLM is called; no
production file is changed. See
`docs/evaluation/MILESTONE_11_G12_VALIDATOR_SAFETY_HARDENING.md`.

Two independent pieces:

1. `validate_candidate_hardened()` -- G11's `validate_candidate()` with
   ONLY its necessity step replaced by `assess_necessity()`. Span,
   classification, concept-resolution and grouping checks are G11's own,
   reused unchanged (so G11's concept-group safeguards cannot weaken
   here). The committed G11 validator itself is left untouched as the
   measured "before" baseline.

2. A concept-correctness CONTRACT that keeps six properties apart:
   (A) valid concept identifier, (B) valid graph relationship,
   (C) source-grounded assignment -- all three automatically checkable by
   `automatic_concept_properties()`, which takes NO gold -- versus
   (D) semantic correctness, which only `evaluate_concept_against_gold()`
   can judge, from INDEPENDENT gold annotations a live validator never
   has. (E) GitHub assessability is a property of the concept node and
   (F) repository support is a property of a candidate's evidence; this
   module never derives F from anything.

`assess_necessity()` is deliberately bounded. It does not parse English;
it restricts where cited evidence may come from and declines to UNKNOWN
whenever a small set of explicit cues (negation, history, hedging,
conditions, quotation, instructions, contradiction) makes the cited
marker unsafe to trust. Every limitation it cannot address is listed in
the milestone doc and fails toward UNKNOWN wherever the cue is visible.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT / "src", _REPO_ROOT / "scripts" / "evaluation_lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from gitscore.jobs.parsing import necessity as _live_necessity  # noqa: E402
from gitscore.jobs.parsing.segmentation import _BULLET_PREFIX  # noqa: E402
from gitscore.jobs.types import GithubObservability  # noqa: E402

import m11g10_competency_concept_model as g10  # noqa: E402
import m11g11_structured_extraction_feasibility as g11  # noqa: E402
from m11g11_structured_extraction_feasibility import (  # noqa: E402
    ApplicantClassification,
    CandidateQualification,
    ConceptResolutionStatus,
    ExtractedNecessity,
    ValidationResult,
)

NECESSITY_VALIDATOR_VERSION = 2
"""1 = G11's keyword-within-160-characters check; 2 = this module.
Independent of `g11.EXTRACTION_SCHEMA_VERSION` (still 1): the candidate
CONTRACT is unchanged and fully backward-compatible -- only how its
`necessity_evidence` field is judged changed."""


# ---------------------------------------------------------------------------
# Marker vocabulary -- the live parser's own markers, plus a small,
# explicit validator-only extension. Never a third, independent list.
# ---------------------------------------------------------------------------

_VALIDATOR_REQUIRED_EXTENSION = re.compile(
    r"\brequire[sd]?\b|\brequirements?\b|\bminimum\s+qualifications?\b|\bmust\b",
    re.IGNORECASE,
)
"""Explicit required-language forms the live parser's `_REQUIRED_MARKER`
does not list (it relies on section headings for them): the verb
'requires', the 'Requirements' / 'Minimum qualifications' heading labels,
and bare 'must'. Validator-only; the live parser's rules are untouched."""

_MARKERS: dict[ExtractedNecessity, tuple[re.Pattern[str], ...]] = {
    ExtractedNecessity.REQUIRED: (_live_necessity._REQUIRED_MARKER, _VALIDATOR_REQUIRED_EXTENSION),
    ExtractedNecessity.PREFERRED: (_live_necessity._PREFERRED_MARKER,),
}

_OPPOSITE = {
    ExtractedNecessity.REQUIRED: ExtractedNecessity.PREFERRED,
    ExtractedNecessity.PREFERRED: ExtractedNecessity.REQUIRED,
}

# Cues are matched in a short window immediately BEFORE a marker, never
# across a clause boundary.
_NEGATION_CUE = re.compile(r"\b(?:not|no|never|without|neither|nor)\b|n't\b", re.IGNORECASE)
_HISTORICAL_CUE = re.compile(
    r"\b(?:was|were|previously|formerly|used\s+to|in\s+the\s+past|had\s+been)\b", re.IGNORECASE
)
_PRE_MARKER_WINDOW_CHARS = 40

# Cues matched anywhere in the claim unit.
_HEDGE_CUE = re.compile(
    r"\b(?:may|might|could|possibly|sometimes|in\s+some\s+cases|depending)\b", re.IGNORECASE
)
_CONDITION_CUE = re.compile(
    r"\b(?:if|unless|when|whenever|except)\b"
    r"|\bfor\s+(?!this\b|the\b|our\b|all\b|any\b)(?:\w+\s+){0,2}"
    r"(?:roles?|positions?|levels?|candidates|applicants|interns|contractors|teams?)\b",
    re.IGNORECASE,
)
_CARVE_OUT_CUE = re.compile(r"\boptional\b", re.IGNORECASE)
_INSTRUCTION_CUE = re.compile(
    r"\b(?:ignore|disregard)\b[^.;\n]*\b(?:instructions?|guidance|above|previous|prior)\b"
    r"|\b(?:system|assistant|user)\s*(?:note|prompt|message)?\s*:"
    r"|\b(?:extractor|classifier|llm|chatbot|automated\s+reviewers?|language\s+model)\b"
    r"|\b(?:mark|label|classify|tag|treat)\s+(?:this|it|every|all|each)\b",
    re.IGNORECASE,
)
_QUOTE_CHARS = '"“”'

# Claim-unit and clause boundaries.
_UNIT_BOUNDARY = re.compile(r"[.!?](?=\s|$)|;|\n")
_CONTRASTIVE_SPLIT = re.compile(
    r",?\s+\b(?:but|while|whereas|although|though|however|yet)\b", re.IGNORECASE
)
_HEADING_SHAPE = re.compile(r"^\s*(?:#{1,6}\s+.+|\*\*[^*]+\*\*\s*:?|[^\n]{1,80}:)\s*$")


@dataclass(frozen=True)
class NecessityAssessment:
    necessity: ExtractedNecessity
    reason: str | None
    evidence_scope: str | None = None  # "claim_unit" | "governing_heading" | None


@dataclass(frozen=True)
class _Region:
    start: int
    end: int


def _claim_unit(job_text: str, s: int, e: int) -> _Region:
    """The sentence/semicolon/line segment containing the span. Its end
    INCLUDES a closing '.', '!', '?' or ';' (so a cited sentence quoted
    with its own terminator stays in scope) but never a newline."""
    start = 0
    for m in _UNIT_BOUNDARY.finditer(job_text, 0, s):
        start = m.end()
    m = _UNIT_BOUNDARY.search(job_text, e)
    if m is None:
        end = len(job_text)
    else:
        end = m.start() if m.group() == "\n" else m.end()
    return _Region(start, end)


def _clause(job_text: str, unit: _Region, s: int, e: int) -> _Region:
    """The contrastive clause ("..., but ...") of the unit containing the span."""
    start, end = unit.start, unit.end
    for m in _CONTRASTIVE_SPLIT.finditer(job_text, unit.start, unit.end):
        if m.end() <= s:
            start = m.end()
        elif m.start() >= e:
            end = min(end, m.start())
            break
    return _Region(start, end)


def _governing_heading(job_text: str, s: int) -> _Region | None:
    """The nearest heading line ABOVE the span's line, when the span sits
    in a list (or directly under the heading). Sibling list items are
    skipped; any other non-blank line ends the search -- a heading never
    governs across ordinary prose, and a heading below the span never
    governs it."""
    line_start = job_text.rfind("\n", 0, s) + 1
    pos = line_start - 1
    while pos > 0:
        prev_start = job_text.rfind("\n", 0, pos) + 1
        line = job_text[prev_start:pos]
        pos = prev_start - 1
        if not line.strip():
            continue
        if _BULLET_PREFIX.match(line):
            continue
        if _HEADING_SHAPE.match(line):
            return _Region(prev_start, prev_start + len(line))
        return None
    return None


def _markers_in(job_text: str, region: _Region, necessity: ExtractedNecessity) -> list[tuple[int, int]]:
    found: set[tuple[int, int]] = set()
    for pattern in _MARKERS[necessity]:
        for m in pattern.finditer(job_text, region.start, region.end):
            found.add((m.start(), m.end()))
    return sorted(found)


def _inside_quotes(job_text: str, region: _Region, pos: int) -> bool:
    count = sum(1 for ch in job_text[region.start:pos] if ch in _QUOTE_CHARS)
    return count % 2 == 1


def _marker_is_live(job_text: str, clause: _Region, marker_start: int) -> str | None:
    """None if the marker is usable; otherwise why not."""
    window = job_text[max(clause.start, marker_start - _PRE_MARKER_WINDOW_CHARS):marker_start]
    if _NEGATION_CUE.search(window):
        return "negated_or_scope_sensitive_marker"
    if _HISTORICAL_CUE.search(window):
        return "historical_marker"
    return None


def _evidence_regions(job_text: str, evidence: str, scopes: list[tuple[str, _Region]]) -> list[tuple[str, _Region]]:
    hits: list[tuple[str, _Region]] = []
    idx = job_text.find(evidence)
    while idx != -1:
        end = idx + len(evidence)
        for name, region in scopes:
            if region.start <= idx and end <= region.end:
                hits.append((name, _Region(idx, end)))
                break
        idx = job_text.find(evidence, idx + 1)
    return hits


def assess_necessity(
    candidate: CandidateQualification,
    job_text: str,
    classification: ApplicantClassification,
) -> NecessityAssessment:
    """Judges ONE candidate's proposed necessity. Pure and deterministic.
    Assumes the span was already verified genuine (G11 step 1). Can only
    KEEP the proposed value or DOWNGRADE it to UNKNOWN -- it never
    promotes UNKNOWN, never switches REQUIRED<->PREFERRED, and never looks
    at the proposed concept."""
    proposed = candidate.proposed_necessity
    if proposed == ExtractedNecessity.UNKNOWN:
        return NecessityAssessment(ExtractedNecessity.UNKNOWN, None)

    def decline(reason: str, scope: str | None = None) -> NecessityAssessment:
        return NecessityAssessment(ExtractedNecessity.UNKNOWN, reason, scope)

    if classification != ApplicantClassification.QUALIFICATION:
        return decline("necessity_not_applicable_to_non_qualification")

    evidence = candidate.necessity_evidence
    if not evidence or not evidence.strip():
        return decline("necessity_evidence_missing")

    s, e = candidate.source_span.start, candidate.source_span.end
    unit = _claim_unit(job_text, s, e)
    clause = _clause(job_text, unit, s, e)
    heading = _governing_heading(job_text, s)

    # 1. Claim-local evidence scope: the cited quote must lie inside the
    #    span's own claim unit or its governing heading -- never in a
    #    neighbouring sentence, sibling bullet, or other section.
    scopes: list[tuple[str, _Region]] = [("claim_unit", unit)]
    if heading is not None:
        scopes.append(("governing_heading", heading))
    hits = _evidence_regions(job_text, evidence, scopes)
    if not hits:
        return decline("necessity_evidence_outside_claim_scope")

    # 2. Instructional / injected text anywhere in the claim scope.
    for name, region in scopes:
        if _INSTRUCTION_CUE.search(job_text, region.start, region.end):
            return decline("instructional_text_in_claim_scope", name)

    # 3. Explicit, live marker of the proposed value, inside the cited
    #    evidence AND inside the span's own clause (or the heading).
    reasons_seen: list[str] = []
    accepted_scope: str | None = None
    for name, ev_region in hits:
        allowed = clause if name == "claim_unit" else heading
        context = unit if name == "claim_unit" else heading
        assert allowed is not None and context is not None
        for ms, me in _markers_in(job_text, ev_region, proposed):
            if not (allowed.start <= ms and me <= allowed.end):
                reasons_seen.append("necessity_marker_outside_span_clause")
                continue
            if _inside_quotes(job_text, context, ms):
                reasons_seen.append("quoted_marker")
                continue
            why = _marker_is_live(job_text, allowed, ms)
            if why:
                reasons_seen.append(why)
                continue
            accepted_scope = name
            break
        if accepted_scope:
            break
    if accepted_scope is None:
        return decline(reasons_seen[0] if reasons_seen else "necessity_evidence_lacks_explicit_marker")

    # 4. Claim-level vetoes: hedging, undeclared conditions, carve-outs,
    #    and contradictory (opposite-tier, non-negated) evidence.
    unit_text = job_text[unit.start:unit.end]
    if _HEDGE_CUE.search(unit_text):
        return decline("hedged_necessity", accepted_scope)
    if _CONDITION_CUE.search(unit_text):
        cond = candidate.applicability_condition
        if not cond or job_text.find(cond, unit.start, unit.end) == -1:
            return decline("conditional_without_declared_condition", accepted_scope)
    if _CARVE_OUT_CUE.search(unit_text):
        return decline("conflicting_necessity_evidence_in_claim", accepted_scope)
    check_regions = [(unit, clause)]
    if accepted_scope == "governing_heading" and heading is not None:
        check_regions.append((heading, heading))
    for region, _ in check_regions:
        for ms, _me in _markers_in(job_text, region, _OPPOSITE[proposed]):
            local_clause = _clause(job_text, region, ms, ms) if region is unit else region
            if _marker_is_live(job_text, local_clause, ms) is None and not _inside_quotes(job_text, region, ms):
                return decline("conflicting_necessity_evidence_in_claim", accepted_scope)

    return NecessityAssessment(proposed, None, accepted_scope)


def validate_candidate_hardened(
    candidate: CandidateQualification,
    job_text: str,
    graph: "g10.CompetencyConceptGraph",
) -> ValidationResult:
    """G11 `validate_candidate()` with only the necessity step replaced."""
    base = g11.validate_candidate(candidate, job_text, graph)
    if not base.span_valid:
        return base
    assessment = assess_necessity(candidate, job_text, base.classification)

    reasons = list(base.decline_reasons)
    if base.necessity_downgrade_reason is not None:
        reasons.remove(base.necessity_downgrade_reason)
    if assessment.reason is not None:
        insert_at = 1 if base.classification_downgrade_reason is not None else 0
        reasons.insert(insert_at, assessment.reason)

    return replace(
        base,
        necessity=assessment.necessity,
        necessity_downgrade_reason=assessment.reason,
        decline_reasons=tuple(reasons),
    )


# ---------------------------------------------------------------------------
# Concept-correctness contract (Phase 4)
# ---------------------------------------------------------------------------


class ConceptCorrectnessOutcome(str, Enum):
    """EVALUATION-ONLY outcomes. Two of them ('gold_confirmed_*') exist only
    because an evaluator holds independent gold; a live validator can
    never produce them."""

    STRUCTURALLY_INVALID_REFERENCE = "structurally_invalid_reference"
    SEMANTICALLY_UNRESOLVED_MAPPING = "semantically_unresolved_mapping"
    GOLD_CONFIRMED_CORRECT = "gold_confirmed_correct"
    GOLD_CONFIRMED_INCORRECT = "gold_confirmed_incorrect"


@dataclass(frozen=True)
class AutomaticConceptProperties:
    """What a validator can check WITHOUT gold. `None` = not applicable."""

    proposes_reference: bool
    valid_concept_identifier: bool | None  # (A)
    valid_graph_relationship: bool | None  # (B) only for alternative groups
    source_grounded_assignment: bool  # (C) genuine span AND accepted as a qualification
    proposed_concept_active: bool | None
    proposed_concept_github_assessable: bool | None  # (E) of the PROPOSED node, not the truth


def _proposal_refs(candidate: CandidateQualification) -> tuple["g10.ConceptRef", ...]:
    p = candidate.proposed_concept
    if p.candidate_ref is not None:
        return (p.candidate_ref,)
    return tuple(p.candidate_alternative_refs)


def automatic_concept_properties(
    result: ValidationResult, graph: "g10.CompetencyConceptGraph"
) -> AutomaticConceptProperties:
    candidate = result.candidate
    refs = _proposal_refs(candidate)
    grounded = result.span_valid and result.accepted_for_review
    if not refs:
        return AutomaticConceptProperties(False, None, None, grounded, None, None)
    nodes = [graph.node(r) for r in refs]
    valid_id = all(n is not None for n in nodes)
    relationship: bool | None = None
    if candidate.proposed_concept.candidate_alternative_refs:
        relationship = result.concept_resolution.status in (
            ConceptResolutionStatus.RESOLVED_ACTIVE,
            ConceptResolutionStatus.RESOLVED_PROVISIONAL,
            ConceptResolutionStatus.RESOLVED_REJECTED,
        )
    active = assessable = None
    if valid_id:
        active = all(n.status == g10.ConceptStatus.ACTIVE for n in nodes)  # type: ignore[union-attr]
        assessable = all(
            n.effective_observability() != GithubObservability.NOT_OBSERVABLE for n in nodes  # type: ignore[union-attr]
        )
    return AutomaticConceptProperties(True, valid_id, relationship, grounded, active, assessable)


@dataclass(frozen=True)
class GoldConceptAnnotation:
    """Independent gold for ONE control. `mapping` is one of "single",
    "alternatives", "absent_from_ontology", "ambiguous",
    "not_a_qualification". `refs` holds the gold ref(s) (or, for
    "ambiguous", the competing readings)."""

    mapping: str
    refs: tuple["g10.ConceptRef", ...] = ()
    candidate_repository_evidence: str = "not_evaluated"  # (F): never derived, only annotated


@dataclass(frozen=True)
class ConceptCorrectnessReport:
    automatic: AutomaticConceptProperties
    outcome: ConceptCorrectnessOutcome
    semantically_correct: bool | None  # (D) from gold only; None when gold cannot decide
    gold_concept_github_assessable: bool | None  # (E) of the TRUE concept
    repository_support: str  # (F) copied from gold, never inferred
    forced_resolution_of_ambiguous_alias: bool
    gold_agrees_unresolved: bool
    note: str


def evaluate_concept_against_gold(
    result: ValidationResult,
    graph: "g10.CompetencyConceptGraph",
    gold: GoldConceptAnnotation,
) -> ConceptCorrectnessReport:
    auto = automatic_concept_properties(result, graph)
    refs = _proposal_refs(result.candidate)
    keys = {r.key for r in refs}
    gold_keys = {r.key for r in gold.refs}

    gold_assessable: bool | None = None
    if gold.mapping in ("single", "alternatives") and gold.refs:
        gold_nodes = [graph.node(r) for r in gold.refs]
        if all(n is not None for n in gold_nodes):
            gold_assessable = all(
                n.effective_observability() != GithubObservability.NOT_OBSERVABLE for n in gold_nodes  # type: ignore[union-attr]
            )

    forced = gold.mapping == "ambiguous" and len(refs) == 1
    gold_agrees_unresolved = not refs and gold.mapping in ("absent_from_ontology", "ambiguous")

    def report(outcome: ConceptCorrectnessOutcome, correct: bool | None, note: str) -> ConceptCorrectnessReport:
        return ConceptCorrectnessReport(
            auto, outcome, correct, gold_assessable, gold.candidate_repository_evidence,
            forced, gold_agrees_unresolved, note,
        )

    if refs and (auto.valid_concept_identifier is False or auto.valid_graph_relationship is False):
        matches_gold = gold.mapping in ("single", "alternatives") and keys == gold_keys
        return report(
            ConceptCorrectnessOutcome.STRUCTURALLY_INVALID_REFERENCE,
            None,
            "proposal violates the G11/G10 reference contract"
            + ("; its reading nonetheless matches gold (contract false decline)" if matches_gold else ""),
        )
    if not refs:
        return report(ConceptCorrectnessOutcome.SEMANTICALLY_UNRESOLVED_MAPPING, None, "no reference proposed")
    if gold.mapping == "ambiguous":
        return report(
            ConceptCorrectnessOutcome.SEMANTICALLY_UNRESOLVED_MAPPING, None,
            "gold is ambiguous; a single forced reading cannot be confirmed",
        )
    if gold.mapping in ("absent_from_ontology", "not_a_qualification"):
        return report(
            ConceptCorrectnessOutcome.GOLD_CONFIRMED_INCORRECT, False,
            f"gold mapping is {gold.mapping!r}; any in-ontology assignment is wrong",
        )
    if keys == gold_keys:
        return report(ConceptCorrectnessOutcome.GOLD_CONFIRMED_CORRECT, True, "matches gold")
    return report(ConceptCorrectnessOutcome.GOLD_CONFIRMED_INCORRECT, False, "valid reference, wrong concept")
