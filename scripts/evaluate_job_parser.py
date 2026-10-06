"""Milestone 8C -- Layer A harness: job-description parser evaluation.

Runs the REAL `parse_job_description()` against every job in
`evaluation/jobs/`, compares against hand-authored gold
(`evaluation/gold/jobs/`), and writes a deterministic report.

Usage:
    python scripts/evaluate_job_parser.py                      # 8c:v1 (frozen), the default
    python scripts/evaluate_job_parser.py --corpus-version 8c:v1.1

Milestone 8D.1: `--corpus-version 8c:v1.1` evaluates against
`evaluation/gold_v1_1/jobs/` instead -- the semantically corrected
benchmark for the concepts this milestone registered (see
docs/evaluation/MILESTONE_8D1_PARSER_IMPROVEMENTS.md). The original
`evaluation/gold/jobs/` (`8c:v1`) is never edited in place; running with
no flag reproduces the exact, byte-for-byte-unchanged `8c:v1` report.

Exit code: 0 on a successful run (REGARDLESS of how many evaluation
findings it reports -- those are measurements, not test failures), 1
only for a harness/fixture-level error (a missing/malformed corpus
file, or an unrecognized --corpus-version value).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from evaluation_lib import parser_eval, report, taxonomy as tax
from evaluation_lib.loaders import (
    GOLD_JOBS_DIR,
    GOLD_JOBS_DIR_V1_1,
    EvaluationFixtureError,
    list_job_ids,
    load_job_and_gold,
)

REPORT_DIR = REPO_ROOT / "evaluation" / "reports"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # Milestone 8D.1: defaults to the frozen `8c:v1` gold (identical
    # behavior/report filenames to every pre-8D.1 caller); pass
    # `--corpus-version 8c:v1.1` to evaluate against the semantically
    # corrected `evaluation/gold_v1_1/jobs/` snapshot instead -- see
    # docs/evaluation/MILESTONE_8D1_PARSER_IMPROVEMENTS.md.
    corpus_version = tax.EVALUATION_CORPUS_VERSION  # "8c:v1"
    report_suffix = ""
    if "--corpus-version" in argv:
        corpus_version = argv[argv.index("--corpus-version") + 1]
    if corpus_version == "8c:v1.1":
        gold_jobs_dir = GOLD_JOBS_DIR_V1_1
        report_suffix = "_v1_1"
    elif corpus_version == tax.EVALUATION_CORPUS_VERSION:
        gold_jobs_dir = GOLD_JOBS_DIR
    else:
        print(
            f"HARNESS ERROR: unknown --corpus-version {corpus_version!r} "
            f"(expected {tax.EVALUATION_CORPUS_VERSION!r} or '8c:v1.1')",
            file=sys.stderr,
        )
        return 1

    try:
        job_ids = list_job_ids()
        if not job_ids:
            raise EvaluationFixtureError("no job files found under evaluation/jobs/")
        jobs_and_gold = [load_job_and_gold(job_id, gold_jobs_dir=gold_jobs_dir) for job_id in job_ids]
    except EvaluationFixtureError as exc:
        print(f"HARNESS ERROR: {exc}", file=sys.stderr)
        return 1

    results = parser_eval.evaluate_jobs(jobs_and_gold)
    metrics = parser_eval.aggregate_metrics(results)

    json_report = {
        "corpus_version": corpus_version,
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
    report.write_json_report(REPORT_DIR / f"parser_report{report_suffix}.json", json_report)

    lines = [
        "# Parser Evaluation Report",
        "",
        f"Corpus version: `{corpus_version}`",
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

    report.write_text_report(REPORT_DIR / f"parser_report{report_suffix}.md", lines)

    print(f"Corpus version: {corpus_version}")
    print(f"Evaluated {metrics['total_jobs']} jobs, {metrics['total_expected_requirements']} expected requirements.")
    print(f"Status counts: {metrics['status_counts']}")
    print(f"Recall={metrics['recall']} Precision={metrics['precision']}")
    print(f"Reports written to {REPORT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
