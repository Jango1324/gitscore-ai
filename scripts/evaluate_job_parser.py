"""Milestone 8C -- Layer A harness: job-description parser evaluation.

Runs the REAL `parse_job_description()` against every job in
`evaluation/jobs/`, compares against hand-authored gold
(`evaluation/gold/jobs/`), and writes a deterministic report.

Usage:
    python scripts/evaluate_job_parser.py

Exit code: 0 on a successful run (REGARDLESS of how many evaluation
findings it reports -- those are measurements, not test failures), 1
only for a harness/fixture-level error (a missing/malformed corpus
file).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from evaluation_lib import parser_eval, report, taxonomy as tax
from evaluation_lib.loaders import EvaluationFixtureError, list_job_ids, load_job_and_gold

REPORT_DIR = REPO_ROOT / "evaluation" / "reports"


def main() -> int:
    try:
        job_ids = list_job_ids()
        if not job_ids:
            raise EvaluationFixtureError("no job files found under evaluation/jobs/")
        jobs_and_gold = [load_job_and_gold(job_id) for job_id in job_ids]
    except EvaluationFixtureError as exc:
        print(f"HARNESS ERROR: {exc}", file=sys.stderr)
        return 1

    results = parser_eval.evaluate_jobs(jobs_and_gold)
    metrics = parser_eval.aggregate_metrics(results)

    json_report = {
        "corpus_version": tax.EVALUATION_CORPUS_VERSION,
        "aggregate": metrics,
        "jobs": [
            {
                "job_id": r.job_id,
                "role_family": r.role_family,
                "verdicts": [
                    {
                        "claim_text": v.claim_text,
                        "facet": v.facet,
                        "necessity": v.necessity,
                        "status": v.status,
                        "tags": list(v.tags),
                        "expected": v.expected,
                        "notes": v.notes,
                    }
                    for v in r.verdicts
                ],
                "spurious": [
                    {
                        "claim_text": s.claim_text,
                        "concept_id": s.concept_id,
                        "category": s.category,
                        "is_alternative_group": s.is_alternative_group,
                    }
                    for s in r.spurious
                ],
            }
            for r in results
        ],
    }
    report.write_json_report(REPORT_DIR / "parser_report.json", json_report)

    lines = [
        "# Parser Evaluation Report",
        "",
        f"Corpus version: `{tax.EVALUATION_CORPUS_VERSION}`",
        f"Jobs evaluated: {metrics['total_jobs']}",
        f"Expected requirements: {metrics['total_expected_requirements']}",
        f"Recall: {metrics['recall']}  |  Precision: {metrics['precision']}",
        "",
        "## Status counts",
        "",
    ]
    lines += report.markdown_table(
        ["status", "count"],
        sorted(metrics["status_counts"].items(), key=lambda kv: -kv[1]),
    )
    lines += ["", "## Error tag counts (a verdict may carry more than one)", ""]
    lines += report.markdown_table(
        ["tag", "count"],
        sorted(metrics["tag_counts"].items(), key=lambda kv: -kv[1]) or [["(none)", 0]],
    )
    lines += ["", "## Most-missed concepts/terms", ""]
    lines += report.markdown_table(
        ["concept_id / term", "miss count"],
        list(metrics["missed_concepts"].items()) or [["(none)", 0]],
    )
    lines += ["", f"## Spurious requirements: {metrics['total_spurious_requirements']}", ""]
    for result in results:
        for s in result.spurious:
            lines.append(f"- `{result.job_id}` / {s.claim_text!r} -> concept_id={s.concept_id!r} category={s.category!r}")

    report.write_text_report(REPORT_DIR / "parser_report.md", lines)

    print(f"Evaluated {metrics['total_jobs']} jobs, {metrics['total_expected_requirements']} expected requirements.")
    print(f"Status counts: {metrics['status_counts']}")
    print(f"Recall={metrics['recall']} Precision={metrics['precision']}")
    print(f"Reports written to {REPORT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
