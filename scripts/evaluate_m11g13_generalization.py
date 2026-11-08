"""Milestone 11-G13 -- G12 generalization, OR-contract comparison, and
real-text aggregate track.

    python scripts/evaluate_m11g13_generalization.py [--real-text]

Offline and deterministic; no LLM, no network. The private real-text
track is OPT-IN (`--real-text`) and exits with an explicit error naming
the missing paths when the private holdouts are absent. Outputs:

* `evaluation/m11g13/generalization_report.json` -- synthetic G13
  controls (G11 vs G12) and the OR-contract strategy comparison. Fully
  reproducible from committed files.
* `evaluation/m11g13/real_text_track_aggregates.json` -- aggregate counts
  only, written only when the private holdouts are present locally.

The G13 control file must match its freeze (raw bytes, or LF-normalized
bytes after a CRLF checkout -- which one matched is recorded). G12's own
metric functions are reused unchanged, so G12 and G13 numbers are
computed identically.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts" / "evaluation_lib"), str(REPO_ROOT / "scripts")]

import evaluate_m11g12_validator_hardening as ev12  # noqa: E402
import m11g10_competency_concept_model as g10  # noqa: E402
import m11g11_structured_extraction_feasibility as g11  # noqa: E402
import m11g12_validator_hardening as g12  # noqa: E402
import m11g13_or_contract as orc  # noqa: E402
import m11g13_real_text_track as rtt  # noqa: E402

CONTROLS_PATH = REPO_ROOT / "evaluation" / "m11g13" / "generalization_controls.json"
FREEZE_PATH = REPO_ROOT / "evaluation" / "m11g13" / "controls_hash_freeze.json"
REPORT_PATH = REPO_ROOT / "evaluation" / "m11g13" / "generalization_report.json"
REAL_TEXT_PATH = REPO_ROOT / "evaluation" / "m11g13" / "real_text_track_aggregates.json"


def load_frozen_controls() -> tuple[dict, str]:
    raw = CONTROLS_PATH.read_bytes()
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    if hashlib.sha256(raw).hexdigest() == freeze["sha256"]:
        how = "raw_bytes"
    elif hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == freeze["sha256_lf_normalized"]:
        how = "lf_normalized"
    else:
        raise SystemExit("G13 FROZEN CONTROLS CHANGED")
    return json.loads(raw.decode("utf-8")), how


def extra_necessity_metrics(controls: list[dict], results: dict) -> dict:
    nec = [c for c in controls if c["kind"] == "necessity"]
    should_decline = [c for c in nec if c["expected_validator_necessity"] == "unknown"
                      and c["proposal"]["proposed_necessity"] != "unknown"]
    declined = [c["id"] for c in should_decline if results[c["id"]].necessity.value == "unknown"]
    unsafe = [c["id"] for c in nec
              if results[c["id"]].accepted_for_review
              and results[c["id"]].necessity.value != "unknown"
              and results[c["id"]].necessity.value != c["expected_validator_necessity"]]
    genuine = [c for c in nec if c["expected_validator_necessity"] != "unknown"]
    wrongly_declined = [c["id"] for c in genuine if results[c["id"]].necessity.value == "unknown"]
    return {
        "4_safe_unknown_declines": {"count": len(declined), "denominator": len(should_decline)},
        "5_genuine_necessities_declined": {
            "count": len(wrongly_declined), "denominator": len(genuine), "ids": wrongly_declined,
            "of_which_abstention_acceptable": [i for i in wrongly_declined
                                               if next(c for c in nec if c["id"] == i)["abstention_acceptable"]],
        },
        "all_unsafe_necessity_acceptances": {"count": len(unsafe), "denominator": len(nec), "ids": unsafe},
    }


def extra_concept_metrics(controls: list[dict], results: dict, graph) -> dict:
    con = [c for c in controls if c["kind"] == "concept"]
    invalid = []
    for c in con:
        auto = g12.automatic_concept_properties(results[c["id"]], graph)
        if auto.proposes_reference and (auto.valid_concept_identifier is False or auto.valid_graph_relationship is False):
            invalid.append(c)
    rejected = [c["id"] for c in invalid
                if results[c["id"]].concept_resolution.status != g11.ConceptResolutionStatus.RESOLVED_ACTIVE]
    return {"8_structurally_invalid_references_rejected": {
        "count": len(rejected), "denominator": len(invalid), "ids": rejected}}


def run() -> dict:
    data, freeze_match = load_frozen_controls()
    controls = data["controls"]
    graph = g10.build_reference_graph()
    scored = [c for c in controls if c["kind"] in ("necessity", "concept")]
    before = {c["id"]: g11.validate_candidate(ev12.build_candidate(c), c["job_text"], graph) for c in scored}
    after = {c["id"]: g12.validate_candidate_hardened(ev12.build_candidate(c), c["job_text"], graph) for c in scored}

    def phase(results):
        return {
            "necessity": {**ev12.necessity_metrics(controls, results, graph), **extra_necessity_metrics(controls, results)},
            "concept": {**ev12.concept_metrics(controls, results, graph), **extra_concept_metrics(controls, results, graph)},
        }

    or_controls = [c for c in controls if c["kind"] == "or_contract"]
    return {
        "milestone": "M11-G13",
        "controls_sha256": hashlib.sha256(CONTROLS_PATH.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        "controls_freeze_matched_by": freeze_match,
        "independence": data["protocol"]["independence"],
        "control_counts": {
            "necessity": data["necessity_control_count"],
            "concept": data["concept_control_count"],
            "or_contract": data["or_contract_control_count"],
        },
        "before_g11": phase(before),
        "after_g12": phase(after),
        "per_control": {
            c["id"]: {
                "category": c["category"],
                "proposed": c["proposal"]["proposed_necessity"],
                "expected": c.get("expected_validator_necessity"),
                "before": before[c["id"]].necessity.value,
                "after": after[c["id"]].necessity.value,
                "after_reason": after[c["id"]].necessity_downgrade_reason,
                "accepted_after": after[c["id"]].accepted_for_review,
            }
            for c in scored
        },
        "or_contract": orc.compare_strategies(or_controls, graph),
    }


def _line(label: str, d: dict) -> str:
    return f"  {label}: {d['count']}/{d['denominator']}" + (f"  {d['ids']}" if d.get("ids") else "")


def main() -> None:
    report = run()
    REPORT_PATH.write_bytes((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    for ph in ("before_g11", "after_g12"):
        n, c = report[ph]["necessity"], report[ph]["concept"]
        print(f"== {ph}")
        for k in ("1_unsupported_required_accepted", "2_unsupported_preferred_accepted",
                  "4_safe_unknown_declines", "5_genuine_necessities_declined",
                  "4b_non_qualifications_incorrectly_accepted",
                  "6_cross_claim_evidence_contamination_accepted", "all_unsafe_necessity_acceptances"):
            print(_line(k, n[k]))
        p = n["3_correct_explicit_necessity_preserved"]
        print(_line("3_strict_preserved", p["abstention_not_acceptable"]), p["false_declines_abstention_not_acceptable"])
        print(_line("3_soft_preserved", p["abstention_acceptable"]))
        v = n["10_score_eligibility_safety_violations"]
        print(_line("10_isolated", v["necessity_isolated_assuming_assessable_concept"]))
        print(_line("10_in_principle", v["assessable_in_principle"]))
        for k in ("7_concept_reference_validity", "8_concept_assignment_correctness_vs_gold",
                  "automatic_accepts_that_gold_marks_incorrect", "8_structurally_invalid_references_rejected",
                  "9_ambiguous_mapping_declines", "wrong_concept_score_eligible_assessable_in_principle",
                  "wrong_concept_score_eligible_current_matcher"):
            print(_line(k, c[k]))
    print("== OR contract")
    for strat, r in report["or_contract"].items():
        summary = {k: (f"{v['count']}/{v['denominator']}" if isinstance(v, dict) and "count" in v else v)
                   for k, v in r.items() if k != "per_control"}
        print(" ", strat, json.dumps(summary))
    print(f"wrote {REPORT_PATH.relative_to(REPO_ROOT)}")
    if "--real-text" not in sys.argv:
        print("== real-text track NOT run (opt-in: pass --real-text; needs local private M11-D/F/G9 holdouts)")
        return
    real = rtt.run_real_text_track()  # raises SystemExit with the missing paths if absent
    REAL_TEXT_PATH.write_bytes((json.dumps(real, indent=2) + "\n").encode("utf-8"))
    print("== real-text track (aggregates)")
    print("  rows:", real["rows"], "located:", real["rows_located_verbatim"])
    for gen, t in real["totals"].items():
        print(f"  {gen}: {t}")
    print(f"wrote {REAL_TEXT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
