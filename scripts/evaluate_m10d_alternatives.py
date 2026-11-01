"""Milestone 10D Phase 3/5 -- alternative-requirement candidate comparison.

Evaluation-only, additive, read-only against production code. Runs every
control in `evaluation/m10d/alternative_controls.json` through the TODAY,
unmodified production outcome (`baseline_pipeline_result`) and through
each of the three M10D candidate prototypes
(`scripts/evaluation_lib/alternative_classifiers.py`), none of which are
wired into `src/gitscore`.

Per-control scoring (deliberately NOT a flat pass/fail):
- `exact_match` -- the candidate's final, unioned concept-id set equals
  `expected_concept_ids` (when annotated) AND its number of logical
  groups equals `expected_requirement_group_count` (when annotated).
  For a MIXED/unsupported control (`expected_concept_ids: null`), only
  the group-count expectation is checked (there is no "correct" id set
  to compare against -- see the corpus's own `schema_notes`).
- `fabricated` -- the candidate's result carries at least one
  `fabricated` id (an unresolved promotion this project's own shape
  policy would not otherwise justify) -- tracked independently of
  `exact_match` so "lost structure safely" and "actively invented a
  technology" are never collapsed into the same bucket (this project's
  M10B/M10C precedent, directly).
- `regression` -- the control's own annotation says the CURRENT
  baseline already gets it right (`current_baseline_outcome` contains
  "already correct" or "ALREADY CORRECT"), but this candidate's result
  no longer matches -- a candidate that breaks a previously-working
  case.

Reports per-candidate aggregate counts, a candidate-by-category
breakdown, and the two real-posting traces plus the `general_swe_01`
and idiom-fabrication variants called out individually, exactly as
Phase 5 of the milestone brief requires.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from evaluation_lib.alternative_classifiers import (  # noqa: E402
    CandidateResult,
    baseline_pipeline_result,
    candidate_a,
    candidate_ab,
    candidate_b,
    candidate_c,
)

CANDIDATES = {
    "baseline": baseline_pipeline_result,
    "candidate_a": candidate_a,
    "candidate_b": candidate_b,
    "candidate_ab": candidate_ab,
    "candidate_c": candidate_c,
}


def _score(control: dict, result: CandidateResult) -> dict:
    expected_ids = control.get("expected_concept_ids")
    expected_count = control.get("expected_requirement_group_count")
    actual_ids = sorted(result.all_concept_ids)
    actual_count = len(result.groups)

    group_count_ok = expected_count is None or actual_count == expected_count
    if expected_ids is None:
        ids_ok = True
    else:
        ids_ok = actual_ids == sorted(expected_ids)
    exact_match = group_count_ok and ids_ok

    fabricated = bool(result.fabricated_ids)
    baseline_note = control.get("current_baseline_outcome", "")
    already_correct = "already correct" in baseline_note.lower()
    regression = already_correct and not exact_match

    return {
        "exact_match": exact_match,
        "fabricated": fabricated,
        "fabricated_ids": list(result.fabricated_ids),
        "regression": regression,
        "structure": result.structure,
        "actual_concept_ids": actual_ids,
        "actual_group_count": actual_count,
    }


def main() -> None:
    corpus_path = ROOT / "evaluation" / "m10d" / "alternative_controls.json"
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    controls = corpus["controls"]

    report: dict = {
        "corpus_version": corpus["corpus_version"],
        "control_count": len(controls),
        "candidates": {},
        "per_control": {},
    }

    for name, fn in CANDIDATES.items():
        per_control_scores = {}
        totals = {"exact_match": 0, "fabricated": 0, "regression": 0}
        by_category: dict[str, dict] = {}
        for control in controls:
            result = fn(control["text"])
            score = _score(control, result)
            per_control_scores[control["id"]] = score
            totals["exact_match"] += int(score["exact_match"])
            totals["fabricated"] += int(score["fabricated"])
            totals["regression"] += int(score["regression"])

            cat = control["category"]
            bucket = by_category.setdefault(cat, {"total": 0, "exact_match": 0, "fabricated": 0, "regression": 0})
            bucket["total"] += 1
            bucket["exact_match"] += int(score["exact_match"])
            bucket["fabricated"] += int(score["fabricated"])
            bucket["regression"] += int(score["regression"])

        report["candidates"][name] = {
            "totals": totals,
            "control_count": len(controls),
            "by_category": by_category,
        }
        report["per_control"][name] = per_control_scores

    highlight_ids = [
        "m10d-soti-real",
        "m10d-manulife-real",
        "m10d-general-swe-control",
        "m10d-idiom-fabrication-variant",
        "m10d-idiom-fabrication-colon-variant",
    ]
    report["highlighted_traces"] = {
        cid: {name: report["per_control"][name][cid] for name in CANDIDATES}
        for cid in highlight_ids
    }

    # Determinism check: run every candidate against every control a
    # second time and confirm byte-identical results (Phase 3's own
    # required comparison axis).
    determinism_failures = []
    for name, fn in CANDIDATES.items():
        for control in controls:
            first = fn(control["text"])
            second = fn(control["text"])
            if first != second:
                determinism_failures.append((name, control["id"]))
    report["determinism_failures"] = determinism_failures

    out_dir = ROOT / "evaluation" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "m10d_alternatives_report.json"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=False), encoding="utf-8")

    md_lines = ["# M10D alternative-requirement candidate comparison", ""]
    md_lines.append(f"Corpus: `{report['corpus_version']}`, {report['control_count']} controls.")
    md_lines.append("")
    md_lines.append("| Candidate | Exact match | Fabricated | Regression |")
    md_lines.append("|---|---|---|---|")
    for name, data in report["candidates"].items():
        t = data["totals"]
        md_lines.append(
            f"| {name} | {t['exact_match']}/{report['control_count']} | {t['fabricated']} | {t['regression']} |"
        )
    md_lines.append("")
    md_lines.append("## By category")
    for name, data in report["candidates"].items():
        md_lines.append(f"### {name}")
        md_lines.append("| Category | Exact match | Fabricated | Regression |")
        md_lines.append("|---|---|---|---|")
        for cat, bucket in sorted(data["by_category"].items()):
            md_lines.append(
                f"| {cat} | {bucket['exact_match']}/{bucket['total']} | {bucket['fabricated']} | {bucket['regression']} |"
            )
        md_lines.append("")
    md_lines.append("## Highlighted traces")
    for cid, per_candidate in report["highlighted_traces"].items():
        md_lines.append(f"### {cid}")
        md_lines.append("| Candidate | Structure | Concept ids | Fabricated |")
        md_lines.append("|---|---|---|---|")
        for name, score in per_candidate.items():
            md_lines.append(
                f"| {name} | {score['structure']} | {', '.join(score['actual_concept_ids']) or '(none)'} | {', '.join(score['fabricated_ids']) or '(none)'} |"
            )
        md_lines.append("")
    md_lines.append(f"Determinism failures: {len(determinism_failures)}")
    md_path = out_dir / "m10d_alternatives_report.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    for name, data in report["candidates"].items():
        t = data["totals"]
        print(f"{name:14s} exact_match={t['exact_match']}/{report['control_count']} fabricated={t['fabricated']} regression={t['regression']}")


if __name__ == "__main__":
    main()
