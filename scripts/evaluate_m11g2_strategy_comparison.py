"""Milestone 11-G2 Phase 3 -- compare Option A/B/C's necessity-decision
accuracy against the frozen G2 corpus's `direct_controls` (the
necessity-decision axis is isolated here from the full extractor's
qualification/tag-matching behavior, which is identical across all
three options and already measured by `evaluate_m11g2_section_context.py`).

Read-only, evaluation-only: no production code is touched by this
script. Writes evaluation/reports/m11g2_strategy_comparison_report.json.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from evaluation_lib.m11g2_section_strategy_prototypes import STRATEGIES  # noqa: E402

CORPUS_PATH = REPO_ROOT / "evaluation" / "m11g2" / "section_context_controls.json"
HASH_FREEZE_PATH = REPO_ROOT / "evaluation" / "m11g2" / "controls_hash_freeze.json"
REPORT_PATH = REPO_ROOT / "evaluation" / "reports" / "m11g2_strategy_comparison_report.json"


def _verify_hash_freeze() -> None:
    freeze = json.loads(HASH_FREEZE_PATH.read_text(encoding="utf-8"))
    actual = hashlib.sha256(CORPUS_PATH.read_bytes()).hexdigest()
    if actual != freeze["sha256"]:
        raise SystemExit(f"G2 CONTROL HASH MISMATCH: expected {freeze['sha256']}, got {actual}.")


def main() -> None:
    _verify_hash_freeze()
    controls = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))["direct_controls"]
    # Necessity-decision only applies to controls that are not expected
    # to decline for an unrelated reason (negation/OR-list-safety) --
    # those are identical across all three options (handled upstream,
    # before necessity is ever computed) and are excluded here.
    relevant = [c for c in controls if not c["expect_decline"]]

    report = {"total_relevant_controls": len(relevant), "strategies": {}}
    for name, fn in STRATEGIES.items():
        correct = 0
        mismatches = []
        for c in relevant:
            actual = fn(c["text"], c["section_kind"], c["document_has_recognized_heading"])
            expected = c["expect_necessity"]
            if actual == expected:
                correct += 1
            else:
                mismatches.append({"id": c["id"], "category": c["category"], "expected": expected, "actual": actual})
        report["strategies"][name] = {
            "correct": correct, "total": len(relevant), "mismatches": mismatches,
        }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    for name, result in report["strategies"].items():
        print(f"{name}: {result['correct']}/{result['total']} correct")
        for m in result["mismatches"]:
            print(f"  MISMATCH {m['id']} ({m['category']}): expected={m['expected']} actual={m['actual']}")
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
