"""Milestone 11-G3 Phase 5 -- end-to-end offline pathway evaluation.

Runs the REAL, unmodified chain:

  raw description -> segment_description() -> section provenance
  -> extract_competency_qualifications_v2(..., has_section_context=True)
  -> Qualification objects -> project_qualification()
  -> JobRequirement / UnparsedClaim

against the frozen, pre-verified `evaluation/m11g3/full_posting_controls.json`
corpus (hash-verified first). This is an INTEGRATION-CORRECTNESS check
against synthetic development controls -- NOT a held-out generalization
claim (see the design doc's own explicit disclaimer).

Reports every metric named in M11-G3 Phase 5, each with raw TP/FP/FN
counts (never a bare percentage), plus the qualification-intent (A-F)
breakdown Phase 3 requires.

Writes evaluation/reports/m11g3_end_to_end_report.json.
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
from gitscore.jobs.parsing.segmentation import (  # noqa: E402
    document_has_any_recognized_heading,
    segment_description,
)

CORPUS_PATH = REPO_ROOT / "evaluation" / "m11g3" / "full_posting_controls.json"
HASH_FREEZE_PATH = REPO_ROOT / "evaluation" / "m11g3" / "controls_hash_freeze.json"
REPORT_PATH = REPO_ROOT / "evaluation" / "reports" / "m11g3_end_to_end_report.json"


def _verify_hash_freeze() -> None:
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "evaluation_lib"))
    from gold_integrity import FreezeIntegrityError, verify_frozen_file  # M11-G14: line-ending-portable
    try:
        verify_frozen_file(CORPUS_PATH, HASH_FREEZE_PATH)
    except FreezeIntegrityError as exc:
        raise SystemExit(f"G3 CONTROL HASH MISMATCH: {exc}") from exc


def main() -> None:
    _verify_hash_freeze()
    data = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))

    # 1. Applicant-qualification identification (claim-level: did the
    #    extractor produce >=1 Qualification for a genuinely-A-labeled,
    #    competency-relevant claim, vs. correctly declining a non-A one).
    qual_tp = qual_fp = qual_fn = qual_tn = 0
    out_of_scope_correct_decline = out_of_scope_total = 0
    # 2/3. Technical-competency detection + tag prediction, PREDICTION-level
    #    (M11-F Phase 1's corrected methodology: every (claim, tag) pair).
    tag_tp = tag_fp = tag_fn = 0
    # 4. Necessity classification (REQUIRED/PREFERRED/UNKNOWN), over every
    #    produced Qualification with a defined expectation.
    necessity_correct = necessity_total = 0
    # 5. Responsibility-vs-qualification: does a B-labeled claim ever get
    #    a CONFIDENT (non-None) necessity -- i.e. a "false qualification"?
    false_qualification_count = 0
    # 6. Narrative/learning false positives: same question for C/D.
    narrative_learning_false_positive_count = 0
    # Claims where a Qualification WAS constructed despite a B/C/D/E
    # ground truth, but safely with necessity=None (the G2-disclosed,
    # accepted tradeoff) -- tracked separately, never conflated with #5/#6.
    safe_nonqualification_construction_count = 0
    # 7. Logical grouping correctness.
    logic_correct = logic_total = 0
    # 8. Source-span exactness.
    span_correct = span_total = 0
    # 9. Conservative projection correctness (job_requirement vs
    #    unparsed_claim + unsafe_reason).
    projection_correct = projection_total = 0
    # 10. Unsupported/declined cases, by reason.
    decline_reasons: dict[str, int] = {}
    no_claim_correct = no_claim_total = 0

    intent_category_counts: dict[str, dict[str, int]] = {}
    mismatches = []

    for posting in data["postings"]:
        description = posting["description"]
        claims = segment_description(description)
        doc_heading = document_has_any_recognized_heading(description)
        by_text = {cl.text: cl for cl in claims}

        for control in posting["controls"]:
            target = control["target_text"]
            category = control["category"]
            bucket = intent_category_counts.setdefault(category, {"total": 0, "matched_expectation": 0})
            bucket["total"] += 1

            if control.get("expect_no_claim"):
                no_claim_total += 1
                produced = target in by_text
                ok = not produced
                no_claim_correct += int(ok)
                bucket["matched_expectation"] += int(ok)
                if not ok:
                    mismatches.append({"posting": posting["id"], "target": target, "error": "expected no claim, one was produced"})
                continue

            claim = by_text[target]
            span = SourceSpan(claim.start, claim.end)
            result = extract_competency_qualifications_v2(
                claim.text, span, section_kind=claim.section_kind,
                document_has_recognized_heading=doc_heading, has_section_context=True,
            )
            is_decline = isinstance(result, DeclinedExtraction)
            expect_decline = control.get("expect_decline", False)
            category_ok = True

            if is_decline:
                decline_reasons[result.reason] = decline_reasons.get(result.reason, 0) + 1

            if control["category"] == "A" and control["is_competency_relevant"]:
                if not is_decline:
                    qual_tp += 1
                else:
                    qual_fn += 1
                    category_ok = False
            elif control["category"] == "A" and not control["is_competency_relevant"]:
                out_of_scope_total += 1
                if is_decline and result.reason == "no_competency_language":
                    out_of_scope_correct_decline += 1
                else:
                    category_ok = False
            elif control["category"] in ("B", "C", "D"):
                if is_decline:
                    qual_tn += 1
                else:
                    # A Qualification WAS constructed for a non-A claim.
                    necessity_val = result[0].necessity
                    if necessity_val is not None:
                        false_qualification_count += 1
                        if control["category"] in ("C", "D"):
                            narrative_learning_false_positive_count += 1
                        category_ok = False
                    else:
                        safe_nonqualification_construction_count += 1
                        # still correct per this control's OWN expectation
                        # (it explicitly predicted necessity=None construction)

            # Tag-level prediction metrics (only meaningful for
            # competency-relevant, non-declined-as-unsafe-OR-list controls).
            if control["is_competency_relevant"] and not control.get("expect_decline"):
                expected_tags = set(([control["expect_tag"]] if control.get("expect_tag") else []) + control.get("expect_sibling_tags", []))
                actual_tags = set() if is_decline else {
                    q.normalized_reference.competency_tag for q in result if q.normalized_reference is not None
                }
                tp = len(expected_tags & actual_tags)
                fp = len(actual_tags - expected_tags)
                fn = len(expected_tags - actual_tags)
                tag_tp += tp
                tag_fp += fp
                tag_fn += fn
                if fp or fn:
                    category_ok = False

            if not is_decline:
                for q in result:
                    if control.get("expect_necessity") is not None or control["category"] in ("A", "B", "C"):
                        necessity_total += 1
                        actual_necessity = q.necessity.value.upper() if q.necessity is not None else None
                        if actual_necessity == control.get("expect_necessity"):
                            necessity_correct += 1
                        else:
                            category_ok = False

                    if control.get("expect_logical_composition"):
                        logic_total += 1
                        actual_logic = q.logical_composition.value
                        if actual_logic == control["expect_logical_composition"]:
                            logic_correct += 1
                        else:
                            category_ok = False

                    span_total += 1
                    if q.source_text == claim.text and q.source_span == span:
                        span_correct += 1
                    else:
                        category_ok = False

                    proj = project_qualification(q)
                    projection_total += 1
                    actual_projection = "job_requirement" if proj.job_requirement is not None else "unparsed_claim"
                    expected_projection = control.get("expect_projection")
                    if expected_projection is None or actual_projection == expected_projection:
                        if control.get("expect_unsafe_reason") and proj.unsafe_reason != control["expect_unsafe_reason"]:
                            category_ok = False
                        else:
                            projection_correct += 1
                    else:
                        category_ok = False

            if is_decline != expect_decline:
                category_ok = False
            elif is_decline and result.reason != control.get("expect_reason"):
                category_ok = False

            bucket["matched_expectation"] += int(category_ok)
            if not category_ok:
                mismatches.append({"posting": posting["id"], "target": target, "error": "see per-metric counters"})

    report = {
        "total_postings": len(data["postings"]),
        "total_controls": sum(len(p["controls"]) for p in data["postings"]),
        "applicant_qualification_identification": {
            "true_positives": qual_tp, "false_negatives": qual_fn,
            "true_negatives_correct_declines": qual_tn,
            "false_qualifications_confident_necessity_on_non_A": false_qualification_count,
            "safe_nonqualification_construction_necessity_none": safe_nonqualification_construction_count,
        },
        "out_of_competency_scope_correctly_declined": {
            "numerator": out_of_scope_correct_decline, "denominator": out_of_scope_total,
        },
        "technical_competency_tag_prediction": {
            "true_positives": tag_tp, "false_positives": tag_fp, "false_negatives": tag_fn,
            "precision": {"numerator": tag_tp, "denominator": tag_tp + tag_fp},
            "recall": {"numerator": tag_tp, "denominator": tag_tp + tag_fn},
        },
        "necessity_classification": {"numerator": necessity_correct, "denominator": necessity_total},
        "narrative_and_learning_false_positives": narrative_learning_false_positive_count,
        "logical_grouping": {"numerator": logic_correct, "denominator": logic_total},
        "source_span_exactness": {"numerator": span_correct, "denominator": span_total},
        "conservative_projection_correctness": {"numerator": projection_correct, "denominator": projection_total},
        "unsupported_declined_cases_by_reason": decline_reasons,
        "no_claim_expectations": {"numerator": no_claim_correct, "denominator": no_claim_total},
        "qualification_intent_category_breakdown": intent_category_counts,
        "mismatches": mismatches,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=False), encoding="utf-8")

    print(f"Postings: {report['total_postings']}  Controls: {report['total_controls']}")
    print("Applicant-qualification identification:", report["applicant_qualification_identification"])
    print("Tag prediction:", report["technical_competency_tag_prediction"])
    print(f"Necessity: {necessity_correct}/{necessity_total}")
    print(f"Narrative/learning false positives: {narrative_learning_false_positive_count}")
    print(f"Logical grouping: {logic_correct}/{logic_total}")
    print(f"Source span exactness: {span_correct}/{span_total}")
    print(f"Conservative projection correctness: {projection_correct}/{projection_total}")
    print("Declines by reason:", decline_reasons)
    print(f"No-claim expectations: {no_claim_correct}/{no_claim_total}")
    print("By intent category:", intent_category_counts)
    print(f"Mismatches: {len(mismatches)}")
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
