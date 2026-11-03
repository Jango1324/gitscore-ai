"""Milestone 11-F Phase 4 -- fair, independent comparison of the real,
unmodified v1 (M11-C) and v2 (M11-E) competency extractors against the
genuinely new, frozen holdout corpus acquired and annotated in Phases
2-3 (`evaluation/m11f/holdout_annotations.json`, hash-frozen in
`evaluation/m11f/gold_hash_freeze.json` BEFORE this script was ever
run).

Uses the Phase 1 CORRECTED per-prediction tag-level methodology
(every (control, tag) pair counted individually as TP/FP/FN, folding
any unexpected sibling tag into the precision denominator) as the
primary tag metric -- not M11-E's own original control-level framing.
Also reuses M11-E's own necessity/logical-grouping/source-span/
explicit-decline/by-domain/scoring-safety measurements verbatim for
direct comparability across milestones.

Neither extractor, nor the gold file, nor the live parser/matcher is
modified by this script. Read-only, additive, evaluation-only.

Writes evaluation/reports/m11f_independent_holdout_report.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gitscore.evidence.profile import build_candidate_evidence_profile  # noqa: E402
from gitscore.jobs.models import SourceSpan  # noqa: E402
from gitscore.jobs.parsing.competency_extraction import (  # noqa: E402
    DeclinedExtraction,
    extract_competency_qualifications,
    extract_competency_qualifications_v2,
)
from gitscore.jobs.parsing.qualification import project_qualification  # noqa: E402
from gitscore.matching.engine import match_requirement  # noqa: E402
from gitscore.matching.types import MatchStatus  # noqa: E402

CORPUS_PATH = REPO_ROOT / "evaluation" / "m11f" / "holdout_annotations.json"
HASH_FREEZE_PATH = REPO_ROOT / "evaluation" / "m11f" / "gold_hash_freeze.json"
REPORT_PATH = REPO_ROOT / "evaluation" / "reports" / "m11f_independent_holdout_report.json"

_EMPTY_PROFILE = build_candidate_evidence_profile("m11f-harness", [], [], [])


def _verify_hash_freeze() -> None:
    import hashlib

    freeze = json.loads(HASH_FREEZE_PATH.read_text(encoding="utf-8"))
    actual = hashlib.sha256(CORPUS_PATH.read_bytes()).hexdigest()
    if actual != freeze["sha256"]:
        raise SystemExit(
            f"GOLD HASH MISMATCH: {CORPUS_PATH} has changed since the freeze recorded in "
            f"{HASH_FREEZE_PATH}. Expected {freeze['sha256']}, got {actual}. Refusing to "
            "evaluate against a corpus that may have been altered after freezing."
        )


def _expected_tags(control: dict) -> frozenset[str]:
    tag = control.get("expected_competency_tag")
    tags = set(control.get("sibling_tags", []))
    if tag:
        tags.add(tag)
    return frozenset(tags)


def _evaluate(extractor, controls: list[dict]) -> dict:
    qual_tp = qual_fp = qual_fn = qual_tn = 0
    tag_tp = tag_fp = tag_fn = 0
    exact_set_matches = exact_set_total = 0
    fp_by_category: dict[str, int] = {}
    necessity_total = necessity_correct = 0
    logical_total = logical_correct = 0
    span_total = span_correct = 0
    declines: dict[str, int] = {}
    by_domain: dict[str, dict] = {}
    safety_checks = 0
    never_supported_flag = True
    never_falsely_assessable = True
    mismatches: list[dict] = []

    for control in controls:
        text = control["text"]
        span = SourceSpan(0, len(text))
        result = extractor(text, span)
        is_positive = not isinstance(result, DeclinedExtraction)
        gt_is_qual = control["is_applicant_qualification"]
        gt_category = control["text_category"]
        domain = control.get("domain") or "unspecified"
        bucket = by_domain.setdefault(domain, {"tag_tp": 0, "tag_fp": 0, "tag_fn": 0, "total_competency": 0})

        if isinstance(result, DeclinedExtraction):
            declines[result.reason] = declines.get(result.reason, 0) + 1

        if gt_is_qual:
            if is_positive:
                qual_tp += 1
            else:
                qual_fn += 1
        else:
            if is_positive:
                qual_fp += 1
                fp_by_category[gt_category] = fp_by_category.get(gt_category, 0) + 1
                mismatches.append({"id": control["id"], "error": f"false_positive_{gt_category}"})
            else:
                qual_tn += 1

        if gt_category == "technical_competency":
            expected = _expected_tags(control)
            predicted = frozenset(
                q.normalized_reference.competency_tag for q in result if q.normalized_reference is not None
            ) if is_positive else frozenset()

            bucket["total_competency"] += 1
            c_tp = len(expected & predicted)
            c_fp = len(predicted - expected)
            c_fn = len(expected - predicted)
            tag_tp += c_tp
            tag_fp += c_fp
            tag_fn += c_fn
            bucket["tag_tp"] += c_tp
            bucket["tag_fp"] += c_fp
            bucket["tag_fn"] += c_fn

            exact_set_total += 1
            if predicted == expected:
                exact_set_matches += 1
            else:
                mismatches.append({
                    "id": control["id"], "error": "tag_set_mismatch",
                    "expected": sorted(expected), "predicted": sorted(predicted),
                })

        if is_positive:
            for q in result:
                span_total += 1
                if q.source_text == text and q.source_span is span:
                    span_correct += 1

                gt_necessity = control.get("necessity")
                if gt_necessity is not None and q.necessity is not None:
                    necessity_total += 1
                    if q.necessity.value.upper() == gt_necessity:
                        necessity_correct += 1
                    else:
                        mismatches.append({"id": control["id"], "error": "necessity_mismatch", "expected": gt_necessity, "actual": q.necessity.value})

                gt_logical = control.get("logical_composition")
                if gt_logical is not None:
                    logical_total += 1
                    if q.logical_composition.value == gt_logical:
                        logical_correct += 1
                    else:
                        mismatches.append({"id": control["id"], "error": "logical_composition_mismatch", "expected": gt_logical, "actual": q.logical_composition.value})

                projection = project_qualification(q)
                if projection.job_requirement is not None:
                    safety_checks += 1
                    match = match_requirement(projection.job_requirement, _EMPTY_PROFILE)
                    if match.status == MatchStatus.SUPPORTED:
                        never_supported_flag = False
                        mismatches.append({"id": control["id"], "error": "UNEXPECTED_SUPPORTED"})
                    if not projection.job_requirement.is_technical and match.status != MatchStatus.NOT_ASSESSABLE:
                        never_falsely_assessable = False
                        mismatches.append({"id": control["id"], "error": "FALSELY_ASSESSABLE"})

    return {
        "qualification_detection": {
            "true_positives": qual_tp, "false_positives": qual_fp,
            "false_negatives": qual_fn, "true_negatives": qual_tn,
            "precision": {"numerator": qual_tp, "denominator": qual_tp + qual_fp},
            "recall": {"numerator": qual_tp, "denominator": qual_tp + qual_fn},
        },
        "tag_level_prediction_metrics": {
            "true_positives": tag_tp, "false_positives": tag_fp, "false_negatives": tag_fn,
            "precision": {"numerator": tag_tp, "denominator": tag_tp + tag_fp},
            "recall": {"numerator": tag_tp, "denominator": tag_tp + tag_fn},
        },
        "exact_tag_set_accuracy": {"numerator": exact_set_matches, "denominator": exact_set_total},
        "false_positives_by_non_qualification_category": fp_by_category,
        "necessity_classification": {"numerator": necessity_correct, "denominator": necessity_total},
        "logical_grouping": {"numerator": logical_correct, "denominator": logical_total},
        "source_span_exactness": {"numerator": span_correct, "denominator": span_total},
        "explicit_declines": declines,
        "by_domain": by_domain,
        "scoring_safety": {
            "safety_checks_run": safety_checks,
            "never_supported_with_empty_evidence": never_supported_flag,
            "never_falsely_assessable_without_concept_mapping": never_falsely_assessable,
        },
        "mismatches": mismatches,
    }


def main() -> None:
    _verify_hash_freeze()
    controls = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))["controls"]

    v1 = _evaluate(extract_competency_qualifications, controls)
    v2 = _evaluate(extract_competency_qualifications_v2, controls)

    report = {
        "gold_hash_verified": True,
        "total_controls": len(controls),
        "total_technical_competency_controls": sum(1 for c in controls if c["text_category"] == "technical_competency"),
        "v1_m11c": v1,
        "v2_m11e": v2,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    for label, r in (("v1 (M11-C)", v1), ("v2 (M11-E)", v2)):
        print(f"=== {label} ===")
        q, t, e = r["qualification_detection"], r["tag_level_prediction_metrics"], r["exact_tag_set_accuracy"]
        print(f"  qualification precision: {q['precision']['numerator']}/{q['precision']['denominator']}")
        print(f"  qualification recall:    {q['recall']['numerator']}/{q['recall']['denominator']}")
        print(f"  tag precision (corrected, per-prediction): {t['precision']['numerator']}/{t['precision']['denominator']}")
        print(f"  tag recall    (corrected, per-prediction): {t['recall']['numerator']}/{t['recall']['denominator']}")
        print(f"  exact tag-set accuracy: {e['numerator']}/{e['denominator']}")
        print(f"  false positives by category: {r['false_positives_by_non_qualification_category']}")
        print(f"  necessity: {r['necessity_classification']['numerator']}/{r['necessity_classification']['denominator']}")
        print(f"  logical grouping: {r['logical_grouping']['numerator']}/{r['logical_grouping']['denominator']}")
        print(f"  span exactness: {r['source_span_exactness']['numerator']}/{r['source_span_exactness']['denominator']}")
        print(f"  explicit declines: {r['explicit_declines']}")
        print(f"  scoring safety: {r['scoring_safety']}")
        print(f"  mismatches: {len(r['mismatches'])}")
        print()
    print("By domain (v2 tag-level TP/FP/FN):")
    for domain, stats in sorted(v2["by_domain"].items()):
        print(f"  {domain}: {stats}")
    print(f"\nWrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
