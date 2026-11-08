"""Milestone 11-G13 Phase 4/5 -- offline comparison of OR-group contract
strategies.

Evaluation-only. Nothing here changes G10/G11/G12, the parser, the
matcher, or scoring; nothing in `src/gitscore` imports this module. Each
strategy is SIMULATED: it turns one frozen OR-contract control into the
`JobRequirement` rows it would hand to the existing, unmodified matcher
(or into nothing, when it declines), and the real `match_requirement()`
is then run against a synthetic candidate profile.

Strategies (none is implemented anywhere but here, as a simulation):

* PRODUCTION -- reference only: the live `parse_job_description()` output
  for the same sentence, unchanged.
* A -- G11 as committed: an alternative group is accepted only if every
  pair is an authored EQUIVALENT edge in the G10 graph; anything else is
  declined (no row).
* B -- distinct OR members allowed in G11's existing
  `candidate_alternative_refs` field, each member independently
  validated; projected like production (one group row, technical
  observability). The field keeps its name, so its documented meaning
  silently changes from "equivalent concepts" to "acceptable
  alternatives".
* C -- OR grouping represented separately from concept normalization:
  members carry their own surface text and ref; equivalence (identical
  refs, or G10 EQUIVALENT edges) only COLLAPSES members; a conservative
  adapter projects a group only when the structure is unambiguous and
  every member is currently evidenceable (a registry concept), so an
  alternative GitHub cannot evidence never sits in the denominator.

Every strategy shares the same G12 necessity gate: necessity UNKNOWN
means no scored row, exactly as M11-B projection already requires.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT / "src", _REPO_ROOT / "scripts" / "evaluation_lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from gitscore.concepts import unresolved_concept_id  # noqa: E402
from gitscore.evidence import (  # noqa: E402
    ConfidenceLevel,
    Evidence,
    EvidenceType,
    RepositoryIdentity,
    build_candidate_evidence_profile,
)
from gitscore.jobs import GithubObservability, Importance, JobRequirement, Necessity  # noqa: E402
from gitscore.jobs.models import SourceSpan  # noqa: E402
from gitscore.jobs.parsing.observability import observability_for_technical  # noqa: E402
from gitscore.jobs.parsing.parser import parse_job_description  # noqa: E402
from gitscore.jobs.parsing.qualification import LogicalComposition, QualificationKind  # noqa: E402
from gitscore.matching import MatchStatus, match_requirement  # noqa: E402

import m11g10_competency_concept_model as g10  # noqa: E402
import m11g11_structured_extraction_feasibility as g11  # noqa: E402
import m11g12_validator_hardening as g12  # noqa: E402

STRATEGIES = ("production_reference", "A_equivalent_only", "B_distinct_members_in_g11_field", "C_separate_grouping")

_SENTENCE_END = re.compile(r"[.!?](?=\s|$)")
_AMBIGUOUS_LIST = re.compile(r",\s*[^,]+\s+or\s+", re.IGNORECASE)
_EXPLICIT_ANY_OF = re.compile(r"\b(?:one of|any of|either|at least one)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Representation:
    declined: bool
    reason: str | None
    requirements: tuple[JobRequirement, ...]
    group_semantics: str | None = None  # "alternatives" | "equivalence" | None
    member_provenance: bool = False


def _member_concept_id(ref: dict) -> str | None:
    if "registry_concept_id" in ref:
        return ref["registry_concept_id"]
    if "unresolved_term" in ref:
        return unresolved_concept_id(ref["unresolved_term"])
    return None  # competency tag: not representable on JobRequirement


def _g10_ref(ref: dict) -> "g10.ConceptRef | None":
    if "registry_concept_id" in ref:
        return g10.ConceptRef(registry_concept_id=ref["registry_concept_id"])
    if "competency_tag" in ref:
        return g10.ConceptRef(competency_tag=ref["competency_tag"])
    return None


def _necessity_evidence(control: dict) -> str:
    text, end = control["job_text"], control["span"]["end"]
    m = _SENTENCE_END.search(text, end)
    return text[end:(m.end() if m else len(text))].strip()


def gated_necessity(control: dict, graph) -> Necessity | None:
    """The shared G12 necessity gate, run on the group's own span."""
    s = control["span"]
    proposed = g11.ExtractedNecessity(control["gold_necessity"])
    candidate = g11.CandidateQualification(
        source_text=s["text"],
        source_span=SourceSpan(start=s["start"], end=s["end"]),
        applicant_classification=g11.ApplicantClassification.QUALIFICATION,
        classification_evidence=s["text"],
        proposed_necessity=proposed,
        necessity_evidence=_necessity_evidence(control),
        qualification_kind=QualificationKind.SPECIFIC_TECHNOLOGY,
        proposed_concept=g11.ProposedConceptReference(unresolved_term="or-group"),
    )
    assessment = g12.assess_necessity(candidate, control["job_text"], g11.ApplicantClassification.QUALIFICATION)
    return {"required": Necessity.REQUIRED, "preferred": Necessity.PREFERRED}.get(assessment.necessity.value)


def proposed_composition(control: dict) -> str:
    span = control["span"]["text"].lower()
    if re.search(r"\b(?:or|either)\b", span):
        return "or_any"
    if re.search(r"\band\b", span):
        return "and"
    return "single"


def _row(control: dict, necessity: Necessity, *, concept_id=None, alternatives=()) -> JobRequirement:
    s = control["span"]
    return JobRequirement(
        original_text=s["text"],
        necessity=necessity,
        importance=Importance.MEDIUM,
        github_observability=observability_for_technical(),
        concept_id=concept_id,
        alternative_concept_ids=tuple(alternatives),
        source_span=SourceSpan(start=s["start"], end=s["end"]),
    )


def represent_production(control: dict, graph) -> Representation:
    profile = parse_job_description(control["job_text"])
    span = control["span"]
    rows = tuple(
        r for r in profile.requirements
        if r.source_span is None or (r.source_span.start < span["end"] and span["start"] < r.source_span.end)
    )
    return Representation(False, None, rows, "alternatives" if any(r.alternative_concept_ids for r in rows) else None)


def represent_a(control: dict, graph) -> Representation:
    necessity = gated_necessity(control, graph)
    if necessity is None:
        return Representation(True, "necessity_unknown", ())
    comp = proposed_composition(control)
    refs = [_g10_ref(m["ref"]) for m in control["members"]]
    if comp == "and":
        rows = tuple(_row(control, necessity, concept_id=_member_concept_id(m["ref"])) for m in control["members"]
                     if _member_concept_id(m["ref"]))
        return Representation(False, None, rows)
    if any(r is None for r in refs):
        return Representation(True, "member_not_in_concept_graph", ())
    if len({r.key for r in refs}) == 1:  # aliases of one concept: a G11 extractor emits a single ref
        return Representation(False, None, (_row(control, necessity, concept_id=_member_concept_id(
            control["members"][0]["ref"])),))
    proposal = g11.ProposedConceptReference(candidate_alternative_refs=tuple(refs))
    resolution = g11._resolve_concept(proposal, graph)
    if resolution.status != g11.ConceptResolutionStatus.RESOLVED_ACTIVE:
        return Representation(True, resolution.status.value, ())
    ids = sorted({_member_concept_id(m["ref"]) for m in control["members"]})
    return Representation(False, None, (_row(control, necessity, alternatives=ids),), "equivalence")


def represent_b(control: dict, graph) -> Representation:
    necessity = gated_necessity(control, graph)
    if necessity is None:
        return Representation(True, "necessity_unknown", ())
    comp = proposed_composition(control)
    ids = [_member_concept_id(m["ref"]) for m in control["members"]]
    if any(i is None for i in ids):
        return Representation(True, "member_not_representable", ())
    if comp == "and":
        return Representation(False, None, tuple(_row(control, necessity, concept_id=i) for i in dict.fromkeys(ids)))
    distinct = sorted(set(ids))
    if len(distinct) == 1:
        return Representation(False, None, (_row(control, necessity, concept_id=distinct[0]),))
    # G11's grouping check only asks for an "or" marker and >= 2 members.
    return Representation(False, None, (_row(control, necessity, alternatives=distinct),), "equivalence")


def represent_c(control: dict, graph) -> Representation:
    necessity = gated_necessity(control, graph)
    if necessity is None:
        return Representation(True, "necessity_unknown", (), member_provenance=True)
    span_text = control["span"]["text"]
    comp = proposed_composition(control)
    if comp == "or_any" and re.search(r"\band\b", span_text, re.IGNORECASE):
        return Representation(True, "mixed_and_or_structure", (), member_provenance=True)
    if comp == "or_any" and _AMBIGUOUS_LIST.search(span_text) and not _EXPLICIT_ANY_OF.search(span_text):
        return Representation(True, "ambiguous_list_grouping", (), member_provenance=True)
    if any(m["surface"] not in span_text for m in control["members"]):
        return Representation(True, "member_surface_not_in_span", (), member_provenance=True)

    # Equivalence collapses members; it never creates or widens a group.
    collapsed: list[dict] = []
    for m in control["members"]:
        ref = _g10_ref(m["ref"])
        dup = False
        for kept in collapsed:
            kref = _g10_ref(kept["ref"])
            if m["ref"] == kept["ref"]:
                dup = True
            elif ref is not None and kref is not None and graph.node(ref) and graph.node(kref) \
                    and graph.is_equivalent(ref, kref):
                dup = True
            if dup:
                break
        if not dup:
            collapsed.append(m)

    ids = [_member_concept_id(m["ref"]) for m in collapsed]
    if any(i is None for i in ids):
        return Representation(True, "member_not_representable", (), member_provenance=True)
    if comp == "and":
        return Representation(False, None, tuple(_row(control, necessity, concept_id=i) for i in ids),
                              member_provenance=True)
    if any(not m["ref"].get("registry_concept_id") for m in collapsed):
        # An alternative the evidence pipeline cannot evidence could satisfy
        # the requirement invisibly: never put such a group in the denominator.
        return Representation(True, "alternative_not_currently_evidenceable", (), member_provenance=True)
    if len(ids) == 1:
        return Representation(False, None, (_row(control, necessity, concept_id=ids[0]),), member_provenance=True)
    return Representation(False, None, (_row(control, necessity, alternatives=sorted(ids)),), "alternatives",
                          member_provenance=True)


REPRESENTERS = {
    "production_reference": represent_production,
    "A_equivalent_only": represent_a,
    "B_distinct_members_in_g11_field": represent_b,
    "C_separate_grouping": represent_c,
}


def candidate_profile(concept_ids: list[str]):
    repo = RepositoryIdentity(owner="candidate", name="synthetic")
    items = tuple(
        Evidence(repository=repo, evidence_type=EvidenceType.DEPENDENCY, raw_observation=f"uses {c}",
                 concept_id=c, confidence=ConfidenceLevel.STRONG, extractor_version="m11g13@1")
        for c in concept_ids
    )
    return build_candidate_evidence_profile("candidate", discovered=(repo,), analyzed=(repo,), evidence_items=items)


def evaluate_control(control: dict, strategy: str, graph) -> dict:
    rep = REPRESENTERS[strategy](control, graph)
    profile = candidate_profile(control["candidate_evidence_concepts"])
    matches = [match_requirement(r, profile) for r in rep.requirements]
    assessable = [m for m in matches if m.status != MatchStatus.NOT_ASSESSABLE]
    supported = [m for m in matches if m.status == MatchStatus.SUPPORTED]
    gold_count = control["gold_scored_requirement_count"]
    gold_assessable = control["gold_assessable"]
    gold_sat = control["gold_candidate_satisfies"]

    out = {
        "declined": rep.declined or not rep.requirements,
        "decline_reason": rep.reason,
        "rows": len(rep.requirements),
        "assessable_rows": len(assessable),
        "supported_rows": len(supported),
        "group_semantics": rep.group_semantics,
        "member_provenance": rep.member_provenance,
    }
    # Denominator safety: an assessable row for a requirement gold says
    # GitHub cannot decide (or whose grouping is ambiguous).
    out["denominator_violation"] = bool(assessable) and gold_assessable is not True
    # Structure: does the represented row count match gold when represented?
    out["undercount"] = bool(rep.requirements) and gold_count is not None and len(rep.requirements) < gold_count
    out["overcount"] = bool(rep.requirements) and gold_count is not None and len(rep.requirements) > gold_count
    # False positive: claims the candidate satisfies everything when gold
    # says not, or when gold says the requirement is not decidable.
    claims_all = bool(assessable) and len(supported) == len(assessable) and len(assessable) == len(rep.requirements)
    undercounted = gold_count is not None and len(rep.requirements) < gold_count
    out["false_positive_satisfaction"] = claims_all and (gold_sat is not True or undercounted)
    out["correct_satisfaction"] = (
        gold_assessable is True and gold_count == len(rep.requirements) and len(assessable) == len(rep.requirements)
        and claims_all == bool(gold_sat)
    )
    out["dropped_decidable_requirement"] = gold_assessable is True and gold_count is not None and not assessable
    return out


def propagation_check(strategy: str, graph) -> dict:
    """Control o013's second sentence: 'Kubernetes experience is a plus.'
    The candidate has AWS evidence only. A consumer that reads the OR group
    under its field's DOCUMENTED meaning expands evidence across members
    when that meaning is equivalence (G11's field contract), never when it
    is alternatives."""
    kubernetes_row = JobRequirement(
        original_text="Kubernetes experience", necessity=Necessity.PREFERRED, importance=Importance.MEDIUM,
        github_observability=GithubObservability.STRONGLY_OBSERVABLE, concept_id="infra.kubernetes",
    )
    group_members = ["cloud.aws", "infra.kubernetes"]
    evidence = ["cloud.aws"]
    semantics = {
        "production_reference": "alternatives",
        "A_equivalent_only": None,  # A declines the AWS/Kubernetes group outright
        "B_distinct_members_in_g11_field": "equivalence",
        "C_separate_grouping": "alternatives",
    }[strategy]
    if semantics == "equivalence":
        evidence = sorted(set(evidence) | set(group_members))
    status = match_requirement(kubernetes_row, candidate_profile(evidence)).status
    return {"field_semantics": semantics, "separate_kubernetes_requirement": status.value,
            "false_positive": status == MatchStatus.SUPPORTED}


def compare_strategies(or_controls: list[dict], graph) -> dict:
    result: dict = {}
    for strategy in STRATEGIES:
        per = {c["id"]: evaluate_control(c, strategy, graph) for c in or_controls}
        decidable = [c for c in or_controls if c["gold_assessable"] is True]

        def count(key, controls=or_controls, per=per):
            ids = [c["id"] for c in controls if per[c["id"]][key]]
            return {"count": len(ids), "denominator": len(controls), "ids": ids}

        result[strategy] = {
            "correct_satisfaction_on_decidable": count("correct_satisfaction", decidable),
            "dropped_decidable_requirements": count("dropped_decidable_requirement", decidable),
            "denominator_violations": count("denominator_violation"),
            "false_positive_satisfaction": count("false_positive_satisfaction"),
            "undercount": count("undercount"),
            "overcount": count("overcount"),
            "member_provenance": count("member_provenance"),
            "cross_requirement_propagation": propagation_check(strategy, graph),
            "per_control": per,
        }
    return result
