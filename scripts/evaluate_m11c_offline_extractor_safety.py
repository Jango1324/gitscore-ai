"""Milestone 11-C Phase 4/5 -- offline competency extractor: real-module
measurement + scoring-safety verification.

Evaluation-only, additive, read-only against production code. Runs the
REAL `src/gitscore/jobs/parsing/competency_extraction.py` module (the
Option C winner chosen by `scripts/evaluate_m11c_competency_extraction.py`'s
own Phase 3 comparison) against every example in
`evaluation/m11c/competency_extraction_controls.json`, and reports:

1. The same Phase 3 metric set (recall/precision/necessity/logical
   grouping/multi-split), now measured against the ACTUAL `Qualification`-
   producing implementation rather than the lightweight comparison
   prototype -- confirming the real module did not regress anything the
   prototype measured.
2. Phase 5 scoring-safety verification: for every `Qualification` this
   module produces that safely projects to a `JobRequirement`
   (`project_qualification()`, UNMODIFIED), run the REAL, UNMODIFIED
   `match_requirement()` against an EMPTY candidate evidence profile
   and confirm the result is NEVER `SUPPORTED` and is `NOT_ASSESSABLE`
   whenever `concept_id`/`alternative_concept_ids` is empty (always
   true for a competency-tagged requirement) -- i.e. a technical
   competency can never silently enter the `assessable_count`
   denominator this module has no way to touch anyway (it is never
   wired into `assess_job()`/`match_job()`), verified directly rather
   than assumed.
3. Source-span exactness and determinism across the full corpus.

Writes `evaluation/reports/m11c_offline_extractor_safety_report.json`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gitscore.evidence.profile import build_candidate_evidence_profile  # noqa: E402
from gitscore.jobs.models import SourceSpan  # noqa: E402
from gitscore.jobs.parsing.competency_extraction import DeclinedExtraction, extract_competency_qualifications  # noqa: E402
from gitscore.jobs.parsing.qualification import project_qualification  # noqa: E402
from gitscore.matching.engine import match_requirement  # noqa: E402
from gitscore.matching.types import MatchStatus  # noqa: E402

CORPUS_PATH = REPO_ROOT / "evaluation" / "m11c" / "competency_extraction_controls.json"
REPORT_PATH = REPO_ROOT / "evaluation" / "reports" / "m11c_offline_extractor_safety_report.json"

_COMPETENCY_BEARING = "technical_competency"
_NON_QUALIFICATION_CATEGORIES = {"responsibility", "company_narrative", "learning_opportunity", "administrative"}
_EMPTY_PROFILE = build_candidate_evidence_profile("m11c-harness", [], [], [])


def _load_corpus() -> list[dict]:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))["controls"]


def main() -> None:
    controls = _load_corpus()

    tp = fn = 0
    fp_breakdown = {"responsibility": 0, "company_narrative": 0, "learning_opportunity": 0, "administrative": 0, "negation": 0, "other_baseline": 0, "missing_contract_declined": 0}
    necessity_total = necessity_correct = 0
    logical_total = logical_correct = 0
    span_exact_total = span_exact_correct = 0
    never_supported = True
    never_falsely_assessable = True
    safety_checks_run = 0
    mismatches: list[dict] = []

    for control in controls:
        text = control["text"]
        span = SourceSpan(0, len(text))
        result = extract_competency_qualifications(text, span)
        gt_category = control["text_category"]
        gt_is_qual = control["is_applicant_qualification"]
        predicted_positive = not isinstance(result, DeclinedExtraction)

        if gt_category == _COMPETENCY_BEARING:
            if predicted_positive:
                tp += 1
            elif isinstance(result, DeclinedExtraction) and result.reason == "missing_contract":
                fp_breakdown["missing_contract_declined"] += 1
                fn += 1  # counted as a recall miss, but NOT a false-positive/fabrication -- see report breakdown
            else:
                fn += 1
                mismatches.append({"id": control["id"], "error": "false_negative", "text": text})
        elif not gt_is_qual and gt_category in _NON_QUALIFICATION_CATEGORIES:
            if predicted_positive:
                fp_breakdown[gt_category] += 1
                mismatches.append({"id": control["id"], "error": f"false_positive_{gt_category}", "text": text})
        elif not gt_is_qual and gt_category == "ambiguous" and "negat" in control["category"]:
            if predicted_positive:
                fp_breakdown["negation"] += 1
                mismatches.append({"id": control["id"], "error": "false_positive_negation", "text": text})
        elif control.get("qualification_kind") != "technical_competency":
            if predicted_positive:
                fp_breakdown["other_baseline"] += 1
                mismatches.append({"id": control["id"], "error": "false_positive_baseline_category", "text": text})

        if predicted_positive:
            for qualification in result:
                span_exact_total += 1
                if qualification.source_text == text and qualification.source_span is span:
                    span_exact_correct += 1
                else:
                    mismatches.append({"id": control["id"], "error": "span_or_text_mismatch"})

                if qualification.necessity is not None:
                    necessity_total += 1
                    if qualification.necessity.value.upper() == control["necessity"]:
                        necessity_correct += 1

                logical_total += 1
                if qualification.logical_composition.value == control["logical_composition"]:
                    logical_correct += 1

                projection = project_qualification(qualification)
                safety_checks_run += 1
                if projection.job_requirement is not None:
                    match = match_requirement(projection.job_requirement, _EMPTY_PROFILE)
                    if match.status == MatchStatus.SUPPORTED:
                        never_supported = False
                        mismatches.append({"id": control["id"], "error": "UNEXPECTED_SUPPORTED_WITH_EMPTY_EVIDENCE"})
                    if not projection.job_requirement.is_technical and match.status != MatchStatus.NOT_ASSESSABLE:
                        never_falsely_assessable = False
                        mismatches.append({"id": control["id"], "error": "COMPETENCY_WITHOUT_CONCEPT_MAPPING_WAS_ASSESSABLE"})

    # Determinism across the whole corpus, run twice.
    run_a = [extract_competency_qualifications(c["text"], SourceSpan(0, len(c["text"]))) for c in controls]
    run_b = [extract_competency_qualifications(c["text"], SourceSpan(0, len(c["text"]))) for c in controls]
    deterministic = run_a == run_b

    report = {
        "qualification_recall": {"numerator": tp, "denominator": tp + fn},
        "qualification_precision": {"numerator": tp, "denominator": tp + sum(v for k, v in fp_breakdown.items() if k != "missing_contract_declined")},
        "false_positive_breakdown": fp_breakdown,
        "necessity_classification": {"numerator": necessity_correct, "denominator": necessity_total},
        "logical_grouping": {"numerator": logical_correct, "denominator": logical_total},
        "source_span_exactness": {"numerator": span_exact_correct, "denominator": span_exact_total},
        "deterministic": deterministic,
        "safety_checks_run": safety_checks_run,
        "never_supported_with_empty_evidence": never_supported,
        "never_falsely_assessable_without_concept_mapping": never_falsely_assessable,
        "mismatches": mismatches,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print(f"qualification_recall:    {report['qualification_recall']['numerator']}/{report['qualification_recall']['denominator']}")
    print(f"qualification_precision: {report['qualification_precision']['numerator']}/{report['qualification_precision']['denominator']}")
    print(f"false_positive_breakdown: {fp_breakdown}")
    print(f"necessity_classification: {necessity_correct}/{necessity_total}")
    print(f"logical_grouping: {logical_correct}/{logical_total}")
    print(f"source_span_exactness: {span_exact_correct}/{span_exact_total}")
    print(f"deterministic: {deterministic}")
    print(f"safety_checks_run: {safety_checks_run}")
    print(f"never_supported_with_empty_evidence: {never_supported}")
    print(f"never_falsely_assessable_without_concept_mapping: {never_falsely_assessable}")
    print(f"mismatches: {len(mismatches)}")
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
