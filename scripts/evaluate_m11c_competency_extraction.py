"""Milestone 11-C Phase 3 -- competency-extraction strategy comparison.

Evaluation-only, additive, read-only against production code. Loads
`evaluation/m11c/competency_extraction_controls.json` (45 independently
annotated examples, authored BEFORE this script was written -- see
that file's own `annotation_provenance`), runs all three Phase 3
candidate strategies (`scripts/evaluation_lib/m11c_competency_prototypes.py`)
against every control, and reports EXACT numerator/denominator counts
for every metric Phase 3 named, never only a percentage.

Writes `evaluation/reports/m11c_competency_extraction_report.json`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from evaluation_lib.m11c_competency_prototypes import STRATEGIES  # noqa: E402

CORPUS_PATH = REPO_ROOT / "evaluation" / "m11c" / "competency_extraction_controls.json"
REPORT_PATH = REPO_ROOT / "evaluation" / "reports" / "m11c_competency_extraction_report.json"

_COMPETENCY_BEARING = "technical_competency"
_NON_QUALIFICATION_CATEGORIES = {"responsibility", "company_narrative", "learning_opportunity", "administrative"}


def _load_corpus() -> list[dict]:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))["controls"]


def _predicted_positive(results: tuple) -> bool:
    return any(r.is_applicant_qualification for r in results)


def _evaluate_strategy(name: str, extract, controls: list[dict]) -> dict:
    tp = fn = 0
    fp_breakdown: dict[str, int] = {"responsibility": 0, "company_narrative": 0, "learning_opportunity": 0, "administrative": 0, "negation": 0, "other_baseline": 0}
    necessity_correct = necessity_total = 0
    logical_correct = logical_total = 0
    multi_splitting_correct = multi_splitting_total = 0
    uninterpretable_correctly_declined = uninterpretable_total = 0
    mismatches: list[dict] = []

    for control in controls:
        text = control["text"]
        results = extract(text)
        predicted_positive = _predicted_positive(results)
        gt_category = control["text_category"]
        gt_is_qual = control["is_applicant_qualification"]

        if gt_category == _COMPETENCY_BEARING:
            if predicted_positive:
                tp += 1
            else:
                fn += 1
                mismatches.append({"id": control["id"], "strategy": name, "error": "false_negative", "text": text})

            if predicted_positive:
                positive_result = next(r for r in results if r.is_applicant_qualification)
                necessity_total += 1
                gt_necessity = control["necessity"]
                pred_necessity = positive_result.necessity_guess
                if pred_necessity == gt_necessity:
                    necessity_correct += 1
                else:
                    mismatches.append({"id": control["id"], "strategy": name, "error": "necessity_mismatch", "expected": gt_necessity, "actual": pred_necessity})

                logical_total += 1
                gt_logical = control["logical_composition"]
                if positive_result.logical_composition_guess == gt_logical:
                    logical_correct += 1
                else:
                    mismatches.append({"id": control["id"], "strategy": name, "error": "logical_composition_mismatch", "expected": gt_logical, "actual": positive_result.logical_composition_guess})

                siblings = control.get("sibling_qualifications", [])
                if siblings:
                    multi_splitting_total += 1
                    expected_tags = {control["competency_concept"]["id"]} if control.get("competency_concept") and control["competency_concept"].get("type") == "competency_tag" else set()
                    for s in siblings:
                        if s.get("competency_concept") and s["competency_concept"].get("type") == "competency_tag":
                            expected_tags.add(s["competency_concept"]["id"])
                    found_tags = set(positive_result.competency_tags)
                    if expected_tags and expected_tags.issubset(found_tags):
                        multi_splitting_correct += 1
                    else:
                        mismatches.append({"id": control["id"], "strategy": name, "error": "multi_competency_split_incomplete", "expected": sorted(expected_tags), "actual": sorted(found_tags)})
        elif not gt_is_qual and gt_category in _NON_QUALIFICATION_CATEGORIES:
            if predicted_positive:
                fp_breakdown[gt_category] += 1
                mismatches.append({"id": control["id"], "strategy": name, "error": f"false_positive_{gt_category}", "text": text})
        elif not gt_is_qual and gt_category == "ambiguous" and "negat" in control["category"]:
            if predicted_positive:
                fp_breakdown["negation"] += 1
                mismatches.append({"id": control["id"], "strategy": name, "error": "false_positive_negation", "text": text})
        elif control.get("qualification_kind") == "uninterpretable":
            uninterpretable_total += 1
            if not predicted_positive:
                uninterpretable_correctly_declined += 1
            else:
                mismatches.append({"id": control["id"], "strategy": name, "error": "uninterpretable_wrongly_claimed", "text": text})
        else:
            # Baseline already-solved categories (named_technology, education,
            # experience, nontechnical) -- this extractor must NEVER fire a
            # competency tag on these at all.
            if predicted_positive:
                fp_breakdown["other_baseline"] += 1
                mismatches.append({"id": control["id"], "strategy": name, "error": "false_positive_baseline_category", "text": text})

    fp_total = sum(fp_breakdown.values())
    predicted_positive_total = tp + fp_total

    # Determinism: run twice, compare.
    run_a = [extract(c["text"]) for c in controls]
    run_b = [extract(c["text"]) for c in controls]
    deterministic = run_a == run_b

    return {
        "strategy": name,
        "qualification_recall": {"numerator": tp, "denominator": tp + fn},
        "qualification_precision": {"numerator": tp, "denominator": predicted_positive_total if predicted_positive_total else 0},
        "false_positive_breakdown": fp_breakdown,
        "necessity_classification": {"numerator": necessity_correct, "denominator": necessity_total},
        "logical_grouping": {"numerator": logical_correct, "denominator": logical_total},
        "multi_competency_splitting": {"numerator": multi_splitting_correct, "denominator": multi_splitting_total},
        "uninterpretable_correctly_declined": {"numerator": uninterpretable_correctly_declined, "denominator": uninterpretable_total},
        "deterministic": deterministic,
        "mismatches": mismatches,
    }


def main() -> None:
    controls = _load_corpus()
    results = {name: _evaluate_strategy(name, extract, controls) for name, extract in STRATEGIES.items()}

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")

    for name, r in results.items():
        print(f"=== {name} ===")
        print(f"  qualification_recall:    {r['qualification_recall']['numerator']}/{r['qualification_recall']['denominator']}")
        print(f"  qualification_precision: {r['qualification_precision']['numerator']}/{r['qualification_precision']['denominator']}")
        print(f"  false_positive_breakdown: {r['false_positive_breakdown']}")
        print(f"  necessity_classification: {r['necessity_classification']['numerator']}/{r['necessity_classification']['denominator']}")
        print(f"  logical_grouping:         {r['logical_grouping']['numerator']}/{r['logical_grouping']['denominator']}")
        print(f"  multi_competency_split:   {r['multi_competency_splitting']['numerator']}/{r['multi_competency_splitting']['denominator']}")
        print(f"  uninterpretable_declined: {r['uninterpretable_correctly_declined']['numerator']}/{r['uninterpretable_correctly_declined']['denominator']}")
        print(f"  deterministic: {r['deterministic']}")
        print()
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
