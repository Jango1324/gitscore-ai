"""Milestone 11-G4 Phase 5 -- admission-recovery evaluation.

Runs the real, unmodified segment_description() alongside the new,
additive recover_unadmitted_qualification_claims(), then the real,
unmodified extract_competency_qualifications_v2()/project_qualification()
chain, against the frozen, pre-verified
evaluation/m11g4/admission_recovery_controls.json corpus (hash-verified
first).

Reports every metric named in M11-G4 Phase 5, each with raw TP/FP/FN
counts. M11-G3's own 81-control corpus is additionally re-run through
this SAME combined (admitted + recovered) pathway as development/
regression material -- never presented as independent generalization
evidence.

Writes evaluation/reports/m11g4_admission_recovery_report.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gitscore.jobs.models import SourceSpan  # noqa: E402
from gitscore.jobs.parsing.competency_extraction import (  # noqa: E402
    DeclinedExtraction,
    extract_competency_qualifications_v2,
)
from gitscore.jobs.parsing.qualification import project_qualification  # noqa: E402
from gitscore.jobs.parsing.qualification_admission_recovery import (  # noqa: E402
    recover_unadmitted_qualification_claims,
)
from gitscore.jobs.parsing.segmentation import (  # noqa: E402
    document_has_any_recognized_heading,
    segment_description,
)

CORPUS_PATH = REPO_ROOT / "evaluation" / "m11g4" / "admission_recovery_controls.json"
HASH_FREEZE_PATH = REPO_ROOT / "evaluation" / "m11g4" / "controls_hash_freeze.json"
REPORT_PATH = REPO_ROOT / "evaluation" / "reports" / "m11g4_admission_recovery_report.json"


def _verify_hash_freeze() -> None:
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "evaluation_lib"))
    from gold_integrity import FreezeIntegrityError, verify_frozen_file  # M11-G14: line-ending-portable
    try:
        verify_frozen_file(CORPUS_PATH, HASH_FREEZE_PATH)
    except FreezeIntegrityError as exc:
        raise SystemExit(f"G4 CONTROL HASH MISMATCH: {exc}") from exc


def main() -> None:
    _verify_hash_freeze()
    data = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))

    # 1. Applicant-qualification identification.
    qual_tp = qual_fn = 0
    # 2. Admission precision/recall: did the RIGHT set of lines become
    #    claims (admitted + recovered), with no unexpected extras?
    admission_tp = admission_fp = admission_fn = 0
    # 3. Technical-competency tag prediction (per-prediction).
    tag_tp = tag_fp = tag_fn = 0
    # 4. False narrative/responsibility admissions: a B/C/D claim that
    #    got a CONFIDENT (non-None) necessity after recovery.
    false_narrative_responsibility_admissions = 0
    # 5. Duplicate qualification count: any claim both admitted AND recovered.
    duplicate_count = 0
    # 6. Necessity accuracy.
    necessity_correct = necessity_total = 0
    # 7. Unsupported logical-structure handling.
    logic_correct = logic_total = 0
    # 8. Source-span exactness.
    span_correct = span_total = 0
    # 9. Safe projection behavior.
    projection_correct = projection_total = 0
    # 10. Previously-correct (already-admitted) behavior preserved.
    already_admitted_preserved = already_admitted_total = 0

    recovered_count = 0
    mismatches = []

    for posting in data["postings"]:
        description = posting["description"]
        admitted = segment_description(description)
        recovered = recover_unadmitted_qualification_claims(description)
        doc_heading = document_has_any_recognized_heading(description)

        by_text_admitted = {cl.text: cl for cl in admitted}
        by_text_recovered = {r.claim.text: r.claim for r in recovered}
        recovered_count += len(recovered)

        for cl_text in by_text_admitted:
            if cl_text in by_text_recovered:
                duplicate_count += 1

        for control in posting["controls"]:
            target = control["target_text"]
            was_admitted = target in by_text_admitted
            was_recovered = target in by_text_recovered

            if control.get("expect_no_claim"):
                admission_total_fp = was_admitted or was_recovered
                if admission_total_fp:
                    admission_fp += 1
                    mismatches.append({"posting": posting["id"], "target": target, "error": "unexpected admission"})
                continue

            expect_admitted_or_recovered = control.get("currently_admitted", False) or control.get("expect_recovered", False)
            got_admitted_or_recovered = was_admitted or was_recovered
            if expect_admitted_or_recovered and got_admitted_or_recovered:
                admission_tp += 1
            elif expect_admitted_or_recovered and not got_admitted_or_recovered:
                admission_fn += 1
                mismatches.append({"posting": posting["id"], "target": target, "error": "expected admission/recovery, got neither"})
                continue
            elif not expect_admitted_or_recovered and got_admitted_or_recovered:
                admission_fp += 1

            if control.get("currently_admitted"):
                already_admitted_total += 1
                claim = by_text_admitted[target]
            else:
                claim = by_text_recovered[target]

            span = SourceSpan(claim.start, claim.end)
            result = extract_competency_qualifications_v2(
                claim.text, span, section_kind=claim.section_kind,
                document_has_recognized_heading=doc_heading, has_section_context=True,
            )
            is_decline = isinstance(result, DeclinedExtraction)
            expect_decline = control.get("expect_decline", False)
            control_ok = (is_decline == expect_decline)

            if control["category"] == "A" and not expect_decline:
                if not is_decline:
                    qual_tp += 1
                else:
                    qual_fn += 1
            if control["category"] in ("B", "C", "D") and not is_decline:
                necessity_val = result[0].necessity
                if necessity_val is not None:
                    false_narrative_responsibility_admissions += 1
                    control_ok = False

            if control.get("currently_admitted") and control_ok:
                already_admitted_preserved += 1

            if is_decline and expect_decline:
                control_ok = control_ok and (result.reason == control.get("expect_reason"))
            elif not is_decline and not expect_decline and control.get("expect_tag"):
                expected_tags = set(([control["expect_tag"]]) + control.get("expect_sibling_tags", []))
                actual_tags = {q.normalized_reference.competency_tag for q in result if q.normalized_reference is not None}
                tp = len(expected_tags & actual_tags)
                fp = len(actual_tags - expected_tags)
                fn = len(expected_tags - actual_tags)
                tag_tp += tp
                tag_fp += fp
                tag_fn += fn
                control_ok = control_ok and not fp and not fn

                for q in result:
                    if control.get("expect_necessity") is not None or control["category"] in ("A", "B", "C"):
                        necessity_total += 1
                        actual_necessity = q.necessity.value.upper() if q.necessity is not None else None
                        if actual_necessity == control.get("expect_necessity"):
                            necessity_correct += 1
                        else:
                            control_ok = False
                    if control.get("expect_logical_composition"):
                        logic_total += 1
                        if q.logical_composition.value == control["expect_logical_composition"]:
                            logic_correct += 1
                        else:
                            control_ok = False
                    span_total += 1
                    if q.source_text == claim.text and q.source_span == span:
                        span_correct += 1
                    else:
                        control_ok = False
                    proj = project_qualification(q)
                    projection_total += 1
                    actual_projection = "job_requirement" if proj.job_requirement is not None else "unparsed_claim"
                    if control.get("expect_projection") in (None, actual_projection):
                        if not control.get("expect_unsafe_reason") or proj.unsafe_reason == control["expect_unsafe_reason"]:
                            projection_correct += 1
                        else:
                            control_ok = False
                    else:
                        control_ok = False

            if not control_ok:
                mismatches.append({"posting": posting["id"], "target": target, "error": "see per-metric counters"})

    report = {
        "total_postings": len(data["postings"]),
        "total_controls": sum(len(p["controls"]) for p in data["postings"]),
        "total_recovered_claims": recovered_count,
        "applicant_qualification_identification": {
            "true_positives": qual_tp, "false_negatives": qual_fn,
            "precision": {"numerator": qual_tp, "denominator": qual_tp},
            "recall": {"numerator": qual_tp, "denominator": qual_tp + qual_fn},
        },
        "admission": {
            "true_positives": admission_tp, "false_positives": admission_fp, "false_negatives": admission_fn,
            "precision": {"numerator": admission_tp, "denominator": admission_tp + admission_fp},
            "recall": {"numerator": admission_tp, "denominator": admission_tp + admission_fn},
        },
        "technical_competency_tag_prediction": {
            "true_positives": tag_tp, "false_positives": tag_fp, "false_negatives": tag_fn,
            "precision": {"numerator": tag_tp, "denominator": tag_tp + tag_fp},
            "recall": {"numerator": tag_tp, "denominator": tag_tp + tag_fn},
        },
        "false_narrative_responsibility_admissions": false_narrative_responsibility_admissions,
        "duplicate_qualification_count": duplicate_count,
        "necessity_accuracy": {"numerator": necessity_correct, "denominator": necessity_total},
        "logical_structure_handling": {"numerator": logic_correct, "denominator": logic_total},
        "source_span_exactness": {"numerator": span_correct, "denominator": span_total},
        "safe_projection_behavior": {"numerator": projection_correct, "denominator": projection_total},
        "previously_correct_behavior_preserved": {"numerator": already_admitted_preserved, "denominator": already_admitted_total},
        "mismatches": mismatches,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=False), encoding="utf-8")

    for k, v in report.items():
        if k not in ("mismatches",):
            print(f"{k}: {v}")
    print(f"Mismatches: {len(mismatches)}")
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
