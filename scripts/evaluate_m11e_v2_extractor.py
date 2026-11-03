"""Milestone 11-E Phase 5 -- comprehensive v2 extractor evaluation.

Evaluation-only, additive, read-only against production code. Runs
BOTH the REAL, unmodified v1 (`extract_competency_qualifications`,
M11-C) and the REAL v2 (`extract_competency_qualifications_v2`,
M11-E) against the SAME `evaluation/m11e/paraphrase_development_controls.json`
corpus (92 controls, authored BEFORE either was compared), measuring
every Phase 5 metric with exact numerator/denominator counts, broken
down by technical discipline, plus the Phase 5 observability-safety
check against the REAL matcher.

M11-D's own historical 3/6 precision / 3/59 recall figures are
reported for CONTEXT ONLY (hardcoded from that milestone's own
committed report, never recomputed here, since M11-D's own corpus is
private/already-inspected) -- this script's own measurements are
explicitly development-corpus results, never presented as independent
validation of anything.

Writes `evaluation/reports/m11e_v2_extractor_report.json`.
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

CORPUS_PATH = REPO_ROOT / "evaluation" / "m11e" / "paraphrase_development_controls.json"
REPORT_PATH = REPO_ROOT / "evaluation" / "reports" / "m11e_v2_extractor_report.json"

_M11D_HISTORICAL_CONTEXT = {
    "note": "M11-D's own independent holdout measurement (hardcoded for context only, never recomputed here -- that corpus is private/already-inspected per its own publication-safety disposition).",
    "technical_competency_precision": {"numerator": 3, "denominator": 6},
    "technical_competency_recall": {"numerator": 3, "denominator": 59},
}

_EMPTY_PROFILE = build_candidate_evidence_profile("m11e-harness", [], [], [])


def _load_corpus() -> list[dict]:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))["controls"]


def _evaluate(extractor, controls: list[dict]) -> dict:
    qual_tp = qual_fp = qual_fn = qual_tn = 0
    tag_tp = tag_fn = unexpected_additional_tag_count = 0
    fp_responsibility = fp_narrative = fp_related_unknown = 0
    necessity_total = necessity_correct = 0
    logical_total = logical_correct = 0
    span_total = span_correct = 0
    declines: dict[str, int] = {}
    by_domain: dict[str, dict] = {}
    safety_checks = never_supported = 0
    never_falsely_assessable = True
    never_supported_flag = True
    mismatches: list[dict] = []

    for control in controls:
        text = control["text"]
        span = SourceSpan(0, len(text))
        result = extractor(text, span)
        is_positive = not isinstance(result, DeclinedExtraction)
        gt_is_qual = control["is_applicant_qualification"]
        gt_category = control["text_category"]
        domain = control.get("domain") or "unspecified"
        bucket = by_domain.setdefault(domain, {"tp": 0, "fn": 0, "fp": 0, "total_competency": 0})

        if isinstance(result, DeclinedExtraction):
            declines[result.reason] = declines.get(result.reason, 0) + 1

        # 1. Applicant-qualification detection (is this a qualification AT ALL).
        if gt_is_qual:
            if is_positive:
                qual_tp += 1
            else:
                qual_fn += 1
        else:
            if is_positive:
                qual_fp += 1
                if gt_category == "responsibility":
                    fp_responsibility += 1
                elif gt_category == "company_narrative":
                    fp_narrative += 1
                mismatches.append({"id": control["id"], "error": f"false_positive_{gt_category}"})
            else:
                qual_tn += 1

        if gt_category == "technical_competency":
            expected_tag = control.get("expected_competency_tag")
            expected_relation = control.get("expected_match_relation")
            bucket["total_competency"] += 1

            if expected_relation in ("related_only", "unknown"):
                if is_positive:
                    fp_related_unknown += 1
                    mismatches.append({"id": control["id"], "error": "false_positive_related_or_unknown"})
                continue

            if control.get("logical_composition") in ("or_any", "mixed_unsupported") and expected_tag is None:
                continue  # structural shape, not a tag-matching case -- see M11-E design doc Phase 3

            if not is_positive:
                tag_fn += 1
                bucket["fn"] += 1
                mismatches.append({"id": control["id"], "error": "false_negative"})
                continue

            found_tags = {q.normalized_reference.competency_tag for q in result if q.normalized_reference is not None}
            if expected_tag in found_tags:
                tag_tp += 1
                bucket["tp"] += 1
                unexpected = found_tags - {expected_tag} - set(control.get("sibling_tags", []))
                if unexpected:
                    unexpected_additional_tag_count += 1
                    mismatches.append({"id": control["id"], "error": "unexpected_additional_tag", "tags": sorted(unexpected)})
            else:
                tag_fn += 1
                bucket["fn"] += 1
                mismatches.append({"id": control["id"], "error": "wrong_tag", "found": sorted(found_tags)})

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
            "precision": {"numerator": qual_tp, "denominator": qual_tp + qual_fp},
            "recall": {"numerator": qual_tp, "denominator": qual_tp + qual_fn},
        },
        "competency_tag_assignment": {
            "precision": {"numerator": tag_tp, "denominator": tag_tp + fp_related_unknown},
            "recall": {"numerator": tag_tp, "denominator": tag_tp + tag_fn},
        },
        "unexpected_additional_tag_count": unexpected_additional_tag_count,
        "false_positives": {
            "from_responsibilities": fp_responsibility,
            "from_company_narratives": fp_narrative,
            "from_related_or_unknown_terminology": fp_related_unknown,
        },
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
    controls = _load_corpus()
    v1_result = _evaluate(extract_competency_qualifications, controls)
    v2_result = _evaluate(extract_competency_qualifications_v2, controls)

    report = {
        "m11d_historical_context_only": _M11D_HISTORICAL_CONTEXT,
        "v1_m11c": v1_result,
        "v2_m11e": v2_result,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    for label, r in (("v1 (M11-C)", v1_result), ("v2 (M11-E)", v2_result)):
        print(f"=== {label} ===")
        q = r["qualification_detection"]
        t = r["competency_tag_assignment"]
        print(f"  qualification precision: {q['precision']['numerator']}/{q['precision']['denominator']}")
        print(f"  qualification recall:    {q['recall']['numerator']}/{q['recall']['denominator']}")
        print(f"  tag precision:           {t['precision']['numerator']}/{t['precision']['denominator']}")
        print(f"  tag recall:              {t['recall']['numerator']}/{t['recall']['denominator']}")
        print(f"  unexpected additional tags: {r['unexpected_additional_tag_count']}")
        print(f"  false positives: {r['false_positives']}")
        print(f"  necessity: {r['necessity_classification']['numerator']}/{r['necessity_classification']['denominator']}")
        print(f"  logical grouping: {r['logical_grouping']['numerator']}/{r['logical_grouping']['denominator']}")
        print(f"  span exactness: {r['source_span_exactness']['numerator']}/{r['source_span_exactness']['denominator']}")
        print(f"  explicit declines: {r['explicit_declines']}")
        print(f"  scoring safety: {r['scoring_safety']}")
        print(f"  mismatches: {len(r['mismatches'])}")
        print()
    print("By domain (v2):")
    for domain, stats in sorted(v2_result["by_domain"].items()):
        print(f"  {domain}: {stats}")
    print(f"\nM11-D historical context (not recomputed): {_M11D_HISTORICAL_CONTEXT}")
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
