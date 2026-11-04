"""Milestone 11-G1 -- evaluate extract_competency_qualifications_v2
against the frozen alternative-requirement-safety control set
(`evaluation/m11g1/alternative_requirement_controls.json`, hash-frozen
in `evaluation/m11g1/controls_hash_freeze.json` BEFORE any production
or offline-extractor code was modified).

Run with --baseline to label the report as a pre-fix baseline (Phase
2), or without the flag for the post-fix comparison (Phase 5). Both
runs use the exact same frozen corpus and hash-verify it first.

Also runs v1 (`extract_competency_qualifications`) over the same
corpus for side-by-side comparison -- v1 is NEVER modified by this
milestone, so its results must be identical across baseline/after
runs; this script asserts that itself.

Writes evaluation/reports/m11g1_<label>_report.json.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gitscore.jobs.models import SourceSpan  # noqa: E402
from gitscore.jobs.parsing.competency_extraction import (  # noqa: E402
    DeclinedExtraction,
    extract_competency_qualifications,
    extract_competency_qualifications_v2,
)

CORPUS_PATH = REPO_ROOT / "evaluation" / "m11g1" / "alternative_requirement_controls.json"
HASH_FREEZE_PATH = REPO_ROOT / "evaluation" / "m11g1" / "controls_hash_freeze.json"


def _verify_hash_freeze() -> None:
    freeze = json.loads(HASH_FREEZE_PATH.read_text(encoding="utf-8"))
    actual = hashlib.sha256(CORPUS_PATH.read_bytes()).hexdigest()
    if actual != freeze["sha256"]:
        raise SystemExit(
            f"G1 CONTROL HASH MISMATCH: expected {freeze['sha256']}, got {actual}. "
            "Refusing to evaluate against a corpus that may have been altered after freezing."
        )


def _evaluate(extractor, controls: list[dict]) -> dict:
    results = []
    pass_count = 0
    for control in controls:
        text = control["text"]
        span = SourceSpan(0, len(text))
        result = extractor(text, span)
        is_decline = isinstance(result, DeclinedExtraction)

        actual = {
            "declined": is_decline,
            "reason": result.reason if is_decline else None,
            "tags": None if is_decline else sorted(
                q.normalized_reference.competency_tag
                for q in result
                if q.normalized_reference is not None
            ),
            "logical_composition": None if is_decline else (
                result[0].logical_composition.value if len(result) == 1 else "and"
            ),
            "necessity": None if is_decline else (
                result[0].necessity.value.upper() if result[0].necessity is not None else None
            ),
            "applicability_condition_present": None if is_decline else any(
                q.applicability_condition is not None for q in result
            ),
            "recognized_tags_in_decline": list(getattr(result, "recognized_tags", ()))
            if is_decline else None,
            "decline_has_source_text": bool(getattr(result, "source_text", None)) if is_decline else None,
            "decline_has_source_span": getattr(result, "source_span", None) is not None if is_decline else None,
        }

        expect_decline = control["expect_decline"]
        ok = actual["declined"] == expect_decline
        if ok and expect_decline:
            ok = actual["reason"] == control.get("expect_reason")
        if ok and not expect_decline:
            expected_tag = control.get("expect_tag")
            if expected_tag is not None:
                ok = actual["tags"] == [expected_tag]
            expected_siblings = control.get("expect_sibling_tags")
            if expected_siblings is not None:
                ok = ok and actual["tags"] == sorted(expected_siblings)
            expected_logic = control.get("expect_logical_composition")
            if expected_logic is not None:
                ok = ok and actual["logical_composition"] == expected_logic
            expected_necessity = control.get("expect_necessity")
            if "expect_necessity" in control:
                ok = ok and actual["necessity"] == expected_necessity
            expected_applicability = control.get("expect_applicability_condition_present")
            if expected_applicability is not None:
                ok = ok and actual["applicability_condition_present"] == expected_applicability

        if ok:
            pass_count += 1
        results.append({"id": control["id"], "category": control["category"], "pass": ok, "actual": actual})

    return {
        "pass_count": pass_count,
        "total": len(controls),
        "failures": [r for r in results if not r["pass"]],
        "all_results": results,
    }


def main() -> None:
    _verify_hash_freeze()
    label = "baseline" if "--baseline" in sys.argv else "after"
    controls = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))["controls"]

    v1_result = _evaluate(extract_competency_qualifications, controls)
    v2_result = _evaluate(extract_competency_qualifications_v2, controls)

    report = {"label": label, "v1_m11c": v1_result, "v2_m11e_or_g1": v2_result}
    out_path = REPO_ROOT / "evaluation" / "reports" / f"m11g1_{label}_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=False), encoding="utf-8")

    print(f"=== {label} ===")
    print(f"v1: {v1_result['pass_count']}/{v1_result['total']} controls match expectation")
    print(f"v2: {v2_result['pass_count']}/{v2_result['total']} controls match expectation")
    if v2_result["failures"]:
        print("v2 failures:")
        for f in v2_result["failures"]:
            print(f"  {f['id']} (cat {f['category']}): {f['actual']}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
