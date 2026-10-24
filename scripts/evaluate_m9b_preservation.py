"""Milestone 9B Phase 1 -- CLI entry point for the requirement-
preservation benchmark.

Runs the REAL `parse_job_description()` against the additive
`evaluation/m9b/corpus.json` corpus (never `evaluation/gold/` or
`evaluation/gold_v1_1/`, both of which stay frozen and untouched) and
writes a deterministic report.

Usage:
    python scripts/evaluate_m9b_preservation.py

Exit code: 0 on a successful run (regardless of how many findings it
reports -- those are measurements, not test failures, exactly like
every other scripts/evaluate_*.py harness), 1 only for a missing/
malformed corpus file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from evaluation_lib import preservation_eval, report as report_mod

CORPUS_PATH = REPO_ROOT / "evaluation" / "m9b" / "corpus.json"
REPORT_DIR = REPO_ROOT / "evaluation" / "reports"


def main() -> int:
    if not CORPUS_PATH.exists():
        print(f"HARNESS ERROR: missing {CORPUS_PATH}", file=sys.stderr)
        return 1
    try:
        corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"HARNESS ERROR: malformed JSON in {CORPUS_PATH}: {exc}", file=sys.stderr)
        return 1

    entries = corpus["entries"]
    entries_by_id = {e["id"]: e for e in entries}

    eval_report = preservation_eval.evaluate_corpus(entries)
    metrics = preservation_eval.aggregate_metrics(eval_report, entries_by_id)

    json_report = {
        "corpus_version": corpus["corpus_version"],
        "parser_version_under_test": __import__("gitscore.jobs", fromlist=["JOB_DESCRIPTION_PARSER_VERSION"]).JOB_DESCRIPTION_PARSER_VERSION,
        "metrics": metrics,
        "verdicts": [
            {
                "id": v.entry_id,
                "category": v.category,
                "is_requirement": v.is_requirement,
                "is_technical": v.is_technical,
                "verdict": v.verdict,
                "actual_row_count": v.actual_row_count,
                "actual_summary": v.actual_summary,
                "span_correct": v.span_correct,
            }
            for v in eval_report.verdicts
        ],
    }
    report_mod.write_json_report(REPORT_DIR / "m9b_preservation_report.json", json_report)

    lines = [
        "# Milestone 9B Phase 1 -- Requirement Preservation Benchmark",
        "",
        f"Corpus version: `{corpus['corpus_version']}`  |  Parser version under test: `{json_report['parser_version_under_test']}`",
        "",
        f"Total entries: {metrics['total_entries']} "
        f"({metrics['total_requirement_entries']} requirement claims, "
        f"{metrics['total_non_requirement_entries']} non-requirement prose/headings)",
        "",
        "## Verdict distribution",
        "",
    ]
    lines += report_mod.markdown_table(
        ["Verdict", "Count"],
        sorted(metrics["verdict_counts"].items(), key=lambda kv: -kv[1]),
    )
    lines += ["", "## Metrics (kept separate by design -- see each definition)", ""]
    for key, data in metrics["metrics"].items():
        lines.append(f"### {key}")
        lines.append(f"- Definition: {data['definition']}")
        if "numerator" in data:
            lines.append(f"- Value: {data['value']} ({data['numerator']}/{data['denominator']})")
        else:
            lines.append(f"- Value: {data['value']}")
        lines.append("")

    lines += ["## Per-entry verdicts", ""]
    lines += report_mod.markdown_table(
        ["ID", "Category", "Verdict", "Rows produced", "Actual"],
        [
            [v.entry_id, v.category, v.verdict, v.actual_row_count, v.actual_summary]
            for v in eval_report.verdicts
        ],
    )
    report_mod.write_text_report(REPORT_DIR / "m9b_preservation_report.md", lines)

    print(f"Entries evaluated: {metrics['total_entries']}")
    for key, data in metrics["metrics"].items():
        print(f"  {key}: {data['value']}")
    print(f"Report written to {REPORT_DIR / 'm9b_preservation_report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
