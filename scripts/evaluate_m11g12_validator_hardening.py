"""Milestone 11-G12 -- before/after safety evaluation of the offline
structured-extraction validator.

    python scripts/evaluate_m11g12_validator_hardening.py

Reads the hash-frozen synthetic controls in `evaluation/m11g12/`, runs
the committed G11 validator ("before") and the G12 hardened validator
("after") over every control, and writes
`evaluation/m11g12/before_after_report.json`. Deterministic, offline, no
LLM, no network. Hard-fails if the controls no longer match their freeze.

Score-eligibility is SIMULATED by building an M11-B `Qualification` from
each validated result and calling the existing, standalone
`project_qualification()` (never wired into the live parser). Nothing
here changes or feeds the live matcher/scorer.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts" / "evaluation_lib")]

import m11g10_competency_concept_model as g10  # noqa: E402
import m11g11_structured_extraction_feasibility as g11  # noqa: E402
import m11g12_validator_hardening as g12  # noqa: E402
from gitscore.jobs.models import SourceSpan  # noqa: E402
from gitscore.jobs.parsing.qualification import (  # noqa: E402
    LogicalComposition,
    Qualification,
    QualificationKind,
    project_qualification,
)
from gitscore.jobs.types import GithubObservability, Necessity, ParserConfidence  # noqa: E402

CONTROLS_PATH = REPO_ROOT / "evaluation" / "m11g12" / "validator_controls.json"
FREEZE_PATH = REPO_ROOT / "evaluation" / "m11g12" / "controls_hash_freeze.json"
REPORT_PATH = REPO_ROOT / "evaluation" / "m11g12" / "before_after_report.json"

CONTAMINATION_CATEGORIES = frozenset({"cross_claim_contamination", "cross_sentence", "markdown_structure", "and_or_group"})


def load_frozen_controls() -> dict:
    raw = CONTROLS_PATH.read_bytes()
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    digest = hashlib.sha256(raw).hexdigest()
    if digest != freeze["sha256"]:
        raise SystemExit(f"FROZEN CONTROLS CHANGED: sha256 {digest} != frozen {freeze['sha256']}")
    return json.loads(raw.decode("utf-8"))


def _ref(d: dict) -> "g10.ConceptRef":
    return g10.ConceptRef(competency_tag=d.get("competency_tag"), registry_concept_id=d.get("registry_concept_id"))


def _proposed_concept(d: dict) -> "g11.ProposedConceptReference":
    if "unresolved_term" in d:
        return g11.ProposedConceptReference(unresolved_term=d["unresolved_term"])
    if "alternatives" in d:
        return g11.ProposedConceptReference(candidate_alternative_refs=tuple(_ref(x) for x in d["alternatives"]))
    return g11.ProposedConceptReference(candidate_ref=_ref(d))


def build_candidate(control: dict) -> "g11.CandidateQualification":
    p, s = control["proposal"], control["span"]
    return g11.CandidateQualification(
        source_text=s["text"],
        source_span=SourceSpan(start=s["start"], end=s["end"]),
        applicant_classification=g11.ApplicantClassification(p["applicant_classification"]),
        classification_evidence=p["classification_evidence"],
        proposed_necessity=g11.ExtractedNecessity(p["proposed_necessity"]),
        necessity_evidence=p["necessity_evidence"],
        qualification_kind=QualificationKind(p["qualification_kind"]),
        proposed_concept=_proposed_concept(p["concept"]),
        logical_composition=LogicalComposition(p["logical_composition"]),
        applicability_condition=p["applicability_condition"],
    )


def gold_annotation(control: dict) -> "g12.GoldConceptAnnotation":
    gc = control["gold_concept"]
    refs: tuple = ()
    if gc is not None:
        if "readings" in gc:
            refs = tuple(_ref(x) for x in gc["readings"])
        elif "alternatives" in gc:
            refs = tuple(_ref(x) for x in gc["alternatives"])
        else:
            refs = (_ref(gc),)
    return g12.GoldConceptAnnotation(control["gold_mapping"], refs, control["candidate_repository_evidence"])


_NEC = {"required": Necessity.REQUIRED, "preferred": Necessity.PREFERRED, "unknown": None}


_ISOLATION_REF = g10.ConceptRef(registry_concept_id="infra.docker")


def simulate_projection(result, graph, necessity: str, accepted: bool, *, isolate_necessity: bool = False) -> dict:
    """Would this validated candidate become a scored `JobRequirement`
    under the existing M11-B projection gates, and would the matcher be
    able to assess it?

    `isolate_necessity=True` pretends every candidate carries a resolved,
    strongly observable registry concept, so the result depends ONLY on
    the necessity/classification/grouping/condition gates -- otherwise an
    unresolved concept can mask a necessity failure."""
    out = {"projected": False, "tier": None, "assessable_in_principle": False, "assessable_current_matcher": False}
    if not accepted:
        return out
    status = result.concept_resolution.status
    obs = None
    nref = None
    if isolate_necessity:
        node = graph.node(_ISOLATION_REF)
        obs = node.effective_observability()
        nref = g10.normalized_reference_from_concept_ref(node.ref)
    elif status == g11.ConceptResolutionStatus.RESOLVED_ACTIVE and result.concept_resolution.resolved_ref is not None:
        node = graph.node(result.concept_resolution.resolved_ref)
        obs = node.effective_observability()
        nref = g10.normalized_reference_from_concept_ref(node.ref)
    c = result.candidate
    q = Qualification(
        qualification_kind=c.qualification_kind,
        source_text=c.source_text,
        source_span=c.source_span,
        necessity=_NEC[necessity],
        applicability_condition=c.applicability_condition,
        interpretation_certainty=ParserConfidence.MEDIUM,
        logical_composition=result.grouping,
        normalized_reference=nref,
        github_observability=obs,
    )
    proj = project_qualification(q)
    if proj.job_requirement is None:
        return out
    jr = proj.job_requirement
    out["projected"] = True
    out["tier"] = jr.necessity.value
    out["assessable_in_principle"] = jr.github_observability != GithubObservability.NOT_OBSERVABLE
    out["assessable_current_matcher"] = out["assessable_in_principle"] and (
        jr.concept_id is not None or bool(jr.alternative_concept_ids)
    )
    return out


def _frac(n: int, d: int) -> dict:
    return {"count": n, "denominator": d}


def necessity_metrics(controls: list[dict], results: dict[str, object], graph) -> dict:
    nec = [c for c in controls if c["kind"] == "necessity"]
    m: dict = {}

    def validated(c):
        return results[c["id"]]

    unsup_req = [c for c in nec if c["proposal"]["proposed_necessity"] == "required"
                 and (c["gold_necessity"] != "required" or not c["proposed_evidence_valid"])]
    unsup_pref = [c for c in nec if c["proposal"]["proposed_necessity"] == "preferred"
                  and (c["gold_necessity"] != "preferred" or not c["proposed_evidence_valid"])]
    req_fail = [c["id"] for c in unsup_req if validated(c).necessity.value == "required" and validated(c).accepted_for_review]
    pref_fail = [c["id"] for c in unsup_pref if validated(c).necessity.value == "preferred" and validated(c).accepted_for_review]
    m["1_unsupported_required_accepted"] = {**_frac(len(req_fail), len(unsup_req)), "ids": req_fail}
    m["2_unsupported_preferred_accepted"] = {**_frac(len(pref_fail), len(unsup_pref)), "ids": pref_fail}

    explicit = [c for c in nec if c["expected_validator_necessity"] in ("required", "preferred")]
    strict = [c for c in explicit if not c["abstention_acceptable"]]
    soft = [c for c in explicit if c["abstention_acceptable"]]
    kept = lambda cs: [c for c in cs if validated(c).necessity.value == c["expected_validator_necessity"]]  # noqa: E731
    m["3_correct_explicit_necessity_preserved"] = {
        "all": _frac(len(kept(explicit)), len(explicit)),
        "abstention_not_acceptable": _frac(len(kept(strict)), len(strict)),
        "abstention_acceptable": _frac(len(kept(soft)), len(soft)),
        "false_declines_abstention_not_acceptable": [c["id"] for c in strict if c not in kept(strict)],
        "false_declines_abstention_acceptable": [c["id"] for c in soft if c not in kept(soft)],
    }
    should_accept = [c for c in nec if c["expected_accepted_for_review"] is True]
    declined = [c["id"] for c in should_accept if not validated(c).accepted_for_review]
    should_reject = [c for c in nec if c["expected_accepted_for_review"] is False]
    wrongly_accepted = [c["id"] for c in should_reject if validated(c).accepted_for_review]
    m["4_correct_qualifications_incorrectly_declined"] = {**_frac(len(declined), len(should_accept)), "ids": declined}
    m["4b_non_qualifications_incorrectly_accepted"] = {**_frac(len(wrongly_accepted), len(should_reject)), "ids": wrongly_accepted}

    span_bad = [c["id"] for c in nec if not validated(c).span_valid]
    m["5_source_span_violations"] = {**_frac(len(span_bad), len(nec)), "ids": span_bad}

    contam = [c for c in nec if not c["proposed_evidence_valid"] and c["category"] in CONTAMINATION_CATEGORIES]
    contam_fail = [c["id"] for c in contam if validated(c).necessity.value == c["proposal"]["proposed_necessity"]]
    m["6_cross_claim_evidence_contamination_accepted"] = {**_frac(len(contam_fail), len(contam)), "ids": contam_fail}

    risky = [c for c in nec if c["score_risk_if_wrong"]]
    viol_principle, viol_current, viol_isolated = [], [], []
    for c in risky:
        r = validated(c)
        exp_acc = c["expected_accepted_for_review"]
        exp_accepted = r.accepted_for_review if exp_acc is None else exp_acc
        for isolate, bucket in ((False, None), (True, viol_isolated)):
            actual = simulate_projection(r, graph, r.necessity.value, r.accepted_for_review, isolate_necessity=isolate)
            expected = simulate_projection(
                r, graph, c["expected_validator_necessity"], exp_accepted, isolate_necessity=isolate
            )
            wrong = actual["projected"] and (not expected["projected"] or actual["tier"] != expected["tier"])
            if not wrong:
                continue
            if isolate:
                bucket.append(c["id"])
                continue
            if actual["assessable_in_principle"]:
                viol_principle.append(c["id"])
            if actual["assessable_current_matcher"]:
                viol_current.append(c["id"])
    m["10_score_eligibility_safety_violations"] = {
        "assessable_in_principle": {**_frac(len(viol_principle), len(risky)), "ids": viol_principle},
        "assessable_by_current_matcher": {**_frac(len(viol_current), len(risky)), "ids": viol_current},
        "necessity_isolated_assuming_assessable_concept": {**_frac(len(viol_isolated), len(risky)), "ids": viol_isolated},
    }
    m["necessity_decline_reasons"] = dict(Counter(
        validated(c).necessity_downgrade_reason for c in nec if validated(c).necessity_downgrade_reason
    ))
    return m


def concept_metrics(controls: list[dict], results: dict[str, object], graph) -> dict:
    con = [c for c in controls if c["kind"] == "concept"]
    reports = {c["id"]: g12.evaluate_concept_against_gold(results[c["id"]], graph, gold_annotation(c)) for c in con}
    proposing = [c for c in con if reports[c["id"]].automatic.proposes_reference]
    valid_ids = [c["id"] for c in proposing if reports[c["id"]].automatic.valid_concept_identifier]
    outcomes = Counter(r.outcome.value for r in reports.values())
    decidable = [c for c in con if reports[c["id"]].semantically_correct is not None]
    correct = [c["id"] for c in decidable if reports[c["id"]].semantically_correct]
    ambiguous = [c for c in con if c["gold_mapping"] == "ambiguous"]
    amb_declined = [c["id"] for c in ambiguous if not reports[c["id"]].forced_resolution_of_ambiguous_alias]
    # Automatic validator "accepts" a concept when it resolves ACTIVE on a
    # grounded qualification -- the shape that could be scored.
    auto_ok = [c for c in con if results[c["id"]].concept_resolution.status == g11.ConceptResolutionStatus.RESOLVED_ACTIVE
               and reports[c["id"]].automatic.source_grounded_assignment]
    auto_ok_wrong = [c["id"] for c in auto_ok if reports[c["id"]].semantically_correct is False]
    wrong_scored, wrong_scored_current = [], []
    for c in con:
        r = results[c["id"]]
        proj = simulate_projection(r, graph, r.necessity.value, r.accepted_for_review)
        if proj["projected"] and proj["assessable_in_principle"] and reports[c["id"]].semantically_correct is False:
            wrong_scored.append(c["id"])
            if proj["assessable_current_matcher"]:
                wrong_scored_current.append(c["id"])
    return {
        "7_concept_reference_validity": {**_frac(len(valid_ids), len(proposing)), "valid_ids": valid_ids},
        "8_concept_assignment_correctness_vs_gold": {
            **_frac(len(correct), len(decidable)), "correct_ids": correct,
            "incorrect_ids": [c["id"] for c in decidable if c["id"] not in correct],
        },
        "9_ambiguous_mapping_declines": {**_frac(len(amb_declined), len(ambiguous)), "ids": amb_declined},
        "outcome_counts": dict(outcomes),
        "automatic_accepts_that_gold_marks_incorrect": {**_frac(len(auto_ok_wrong), len(auto_ok)), "ids": auto_ok_wrong},
        "wrong_concept_score_eligible_assessable_in_principle": {**_frac(len(wrong_scored), len(con)), "ids": wrong_scored},
        "wrong_concept_score_eligible_current_matcher": {
            **_frac(len(wrong_scored_current), len(con)), "ids": wrong_scored_current,
        },
        "per_control": {
            cid: {
                "outcome": r.outcome.value,
                "A_valid_identifier": r.automatic.valid_concept_identifier,
                "B_valid_relationship": r.automatic.valid_graph_relationship,
                "C_source_grounded": r.automatic.source_grounded_assignment,
                "D_semantically_correct_gold": r.semantically_correct,
                "E_proposed_assessable": r.automatic.proposed_concept_github_assessable,
                "E_gold_assessable": r.gold_concept_github_assessable,
                "F_repository_support_gold": r.repository_support,
                "note": r.note,
            }
            for cid, r in reports.items()
        },
    }


def run() -> dict:
    data = load_frozen_controls()
    controls = data["controls"]
    graph = g10.build_reference_graph()
    before = {c["id"]: g11.validate_candidate(build_candidate(c), c["job_text"], graph) for c in controls}
    after = {c["id"]: g12.validate_candidate_hardened(build_candidate(c), c["job_text"], graph) for c in controls}
    per_control = {
        c["id"]: {
            "category": c["category"],
            "proposed": c["proposal"]["proposed_necessity"],
            "expected": c.get("expected_validator_necessity"),
            "before": before[c["id"]].necessity.value,
            "after": after[c["id"]].necessity.value,
            "after_reason": after[c["id"]].necessity_downgrade_reason,
            "accepted_before": before[c["id"]].accepted_for_review,
            "accepted_after": after[c["id"]].accepted_for_review,
        }
        for c in controls
    }
    report = {
        "milestone": "M11-G12",
        "controls_sha256": hashlib.sha256(CONTROLS_PATH.read_bytes()).hexdigest(),
        "necessity_validator_version_after": g12.NECESSITY_VALIDATOR_VERSION,
        "control_counts": {"necessity": data["necessity_control_count"], "concept": data["concept_control_count"]},
        "before_g11": {"necessity": necessity_metrics(controls, before, graph), "concept": concept_metrics(controls, before, graph)},
        "after_g12": {"necessity": necessity_metrics(controls, after, graph), "concept": concept_metrics(controls, after, graph)},
        "per_control": per_control,
    }
    return report


def main() -> None:
    report = run()
    REPORT_PATH.write_bytes((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    for phase in ("before_g11", "after_g12"):
        n = report[phase]["necessity"]
        c = report[phase]["concept"]
        print(f"== {phase}")
        for key in ("1_unsupported_required_accepted", "2_unsupported_preferred_accepted",
                    "4_correct_qualifications_incorrectly_declined", "4b_non_qualifications_incorrectly_accepted",
                    "5_source_span_violations", "6_cross_claim_evidence_contamination_accepted"):
            print(f"  {key}: {n[key]['count']}/{n[key]['denominator']}  {n[key].get('ids', '')}")
        p = n["3_correct_explicit_necessity_preserved"]
        print(f"  3_preserved: all {p['all']['count']}/{p['all']['denominator']}; strict "
              f"{p['abstention_not_acceptable']['count']}/{p['abstention_not_acceptable']['denominator']} "
              f"{p['false_declines_abstention_not_acceptable']}; soft {p['abstention_acceptable']['count']}/"
              f"{p['abstention_acceptable']['denominator']} {p['false_declines_abstention_acceptable']}")
        v = n["10_score_eligibility_safety_violations"]
        print(f"  10_score_violations: in_principle {v['assessable_in_principle']['count']}/"
              f"{v['assessable_in_principle']['denominator']} {v['assessable_in_principle']['ids']}; current_matcher "
              f"{v['assessable_by_current_matcher']['count']} {v['assessable_by_current_matcher']['ids']}; "
              f"necessity-isolated {v['necessity_isolated_assuming_assessable_concept']['count']}/"
              f"{v['necessity_isolated_assuming_assessable_concept']['denominator']} "
              f"{v['necessity_isolated_assuming_assessable_concept']['ids']}")
        for key in ("7_concept_reference_validity", "8_concept_assignment_correctness_vs_gold",
                    "9_ambiguous_mapping_declines", "automatic_accepts_that_gold_marks_incorrect",
                    "wrong_concept_score_eligible_assessable_in_principle"):
            print(f"  {key}: {c[key]['count']}/{c[key]['denominator']}")
        print(f"  outcomes: {c['outcome_counts']}")
    print(f"wrote {REPORT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
