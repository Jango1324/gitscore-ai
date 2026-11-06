"""Milestone 11-G6 Phase 1/4 -- measures the REAL, unmodified live
parser's CURRENT behavior against the frozen `heading_controls.json`
corpus, and diffs it against the independently-authored gold.

Evaluation-only. Imports production code read-only; writes no
production code; never mutates gold after its freeze point. Run AFTER
`m11g6_build_heading_controls.py` and the hash freeze -- gold must never
be informed by what this script finds.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gitscore.jobs.parsing.parser import parse_job_description_with_diagnostics  # noqa: E402
from gitscore.jobs.parsing.segmentation import (  # noqa: E402
    _classify_heading_line,
    _line_content_span,
    _SectionKind,
)

GOLD_PATH = REPO_ROOT / "evaluation" / "m11g6" / "heading_controls.json"
FREEZE_PATH = REPO_ROOT / "evaluation" / "m11g6" / "gold_hash_freeze.json"
OUT_PATH = REPO_ROOT / "evaluation" / "reports" / "m11g6_phase1_current_behavior.json"


def current_heading_classification(heading_line: str | None) -> str:
    if heading_line is None:
        return "NOT_A_HEADING"
    span = _line_content_span(heading_line, 0)
    if span is None:
        return "NOT_A_HEADING"
    content = heading_line[span[0]:span[1]]
    classified = _classify_heading_line(heading_line, content)
    return classified.name if classified is not None else "NOT_A_HEADING"


def build_description(control: dict) -> str:
    lines = []
    if control["heading_line"] is not None:
        lines.append(control["heading_line"])
    lines.extend(control["body_lines"])
    return "\n".join(lines) + "\n"


def main() -> None:
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    import hashlib
    actual_hash = hashlib.sha256(GOLD_PATH.read_bytes()).hexdigest()
    assert actual_hash == freeze["sha256"], "gold has drifted since freeze -- aborting"

    rows = []
    mismatches = []
    skip_suppression_mismatches = []

    for control in gold["controls"]:
        description = build_description(control)
        current_kind = current_heading_classification(control["heading_line"])
        expected_kind = control["expected_heading_kind"]
        kind_match = current_kind == expected_kind

        parsed = parse_job_description_with_diagnostics(description)
        n_requirements = len(parsed.profile.requirements)
        n_unparsed = len(parsed.unparsed_claims)
        n_body_lines_expected_to_enter = sum(
            1 for q in control["body_qualifications"] if q["should_enter_assessment"]
        )
        n_admitted_total = n_requirements + n_unparsed
        current_skip_suppression = current_kind == "NON_QUALIFICATION" and n_admitted_total == 0

        row = {
            "id": control["id"],
            "category": control["category"],
            "expected_heading_kind": expected_kind,
            "current_heading_kind": current_kind,
            "heading_kind_matches_gold": kind_match,
            "expected_skip_suppression_appropriate": control["skip_suppression_appropriate"],
            "n_body_lines_total": len(control["body_lines"]),
            "n_body_lines_gold_should_enter_assessment": n_body_lines_expected_to_enter,
            "current_n_job_requirements": n_requirements,
            "current_n_unparsed_claims": n_unparsed,
            "current_n_admitted_total": n_admitted_total,
        }
        rows.append(row)

        if not kind_match:
            mismatches.append(control["id"])

        # The safety-critical check: does current behavior UNRECOVERABLY
        # suppress content gold says should be admissible (SKIP when it
        # should not be), or vice versa (admits content gold says should
        # be fully suppressed)?
        should_be_fully_suppressed = control["skip_suppression_appropriate"]
        if should_be_fully_suppressed and n_admitted_total > 0:
            skip_suppression_mismatches.append({"id": control["id"], "direction": "under-suppressed"})
        if not should_be_fully_suppressed and n_body_lines_expected_to_enter > 0 and n_admitted_total == 0:
            skip_suppression_mismatches.append({"id": control["id"], "direction": "over-suppressed"})

    out = {
        "corpus_version": gold["corpus_version"],
        "gold_hash_verified": actual_hash == freeze["sha256"],
        "n_controls": len(gold["controls"]),
        "n_heading_kind_mismatches": len(mismatches),
        "heading_kind_mismatch_ids": mismatches,
        "n_skip_suppression_mismatches": len(skip_suppression_mismatches),
        "skip_suppression_mismatches": skip_suppression_mismatches,
        "rows": rows,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {len(rows)} rows to {OUT_PATH}")
    print(f"heading-kind mismatches: {len(mismatches)}")
    print(f"skip-suppression (over/under) mismatches: {len(skip_suppression_mismatches)}")


if __name__ == "__main__":
    main()
