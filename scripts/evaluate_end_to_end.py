"""Milestone 8C -- Layers C/D harness: matcher/assessment correctness +
the candidate x job evaluation matrix.

Runs the REAL `match_job()`/`assess_job()` over this evaluation's own
candidate fixtures and job corpus (strategically selected pairs --
`evaluation/gold/matrix.json`, not a full cross product). No live
GitHub call. No "true fit" ground truth is computed or stored (Part 14)
-- `expected_direction` is a pre-registered qualitative sanity check,
reported as prose observations in the final report, never scored.

Usage:
    python scripts/evaluate_end_to_end.py

Exit code: 0 on a successful run, 1 only for a harness/fixture-level
error.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from evaluation_lib import end_to_end_eval, report, taxonomy as tax
from evaluation_lib.loaders import (
    EvaluationFixtureError,
    list_candidate_names,
    list_job_ids,
    load_candidate_fixture,
    load_job,
)

REPORT_DIR = REPO_ROOT / "evaluation" / "reports"
MATRIX_PATH = REPO_ROOT / "evaluation" / "gold" / "matrix.json"


def main() -> int:
    try:
        if not MATRIX_PATH.exists():
            raise EvaluationFixtureError(f"missing {MATRIX_PATH}")
        matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))

        candidate_names = list_candidate_names()
        fixtures = {}
        for pair in matrix["pairs"]:
            name = pair["candidate"]
            # Fixture filenames are lowercase; candidate names in the
            # matrix use their real GitHub casing -- resolve case-insensitively.
            match = next((n for n in candidate_names if n.lower() == name.lower()), None)
            if match is None:
                raise EvaluationFixtureError(f"matrix references unknown candidate fixture: {name}")
            fixtures[name] = load_candidate_fixture(match)

        job_ids = list_job_ids()
        jobs = {job_id: load_job(job_id) for job_id in job_ids}
        for pair in matrix["pairs"]:
            if pair["job_id"] not in jobs:
                raise EvaluationFixtureError(f"matrix references unknown job_id: {pair['job_id']}")
    except EvaluationFixtureError as exc:
        print(f"HARNESS ERROR: {exc}", file=sys.stderr)
        return 1

    candidate_profiles = end_to_end_eval.build_candidate_profiles(fixtures)
    cells = end_to_end_eval.evaluate_matrix(matrix, candidate_profiles, jobs)
    metrics = end_to_end_eval.aggregate_metrics(cells)

    json_report = {
        "corpus_version": tax.EVALUATION_CORPUS_VERSION,
        "aggregate": metrics,
        "cells": [c.__dict__ for c in cells],
    }
    report.write_json_report(REPORT_DIR / "end_to_end_report.json", json_report)

    lines = [
        "# End-to-End Evaluation Matrix Report",
        "",
        f"Corpus version: `{tax.EVALUATION_CORPUS_VERSION}`",
        f"Pairs evaluated: {metrics['pairs_evaluated']}",
        f"Assessment aggregation errors: {metrics['assessment_aggregation_errors']}",
        f"Matcher integrity errors: {metrics['matcher_integrity_errors']}",
        "",
        "## Matrix",
        "",
    ]
    lines += report.markdown_table(
        ["candidate", "job_id", "expected_direction", "alignment", "required", "preferred",
         "supported", "not_observed", "not_assessable", "agg_ok", "matcher_ok"],
        [
            [c.candidate, c.job_id, c.expected_direction, c.alignment_score, c.required, c.preferred,
             c.supported_count, c.not_observed_count, c.not_assessable_count,
             c.aggregation_matches, c.matcher_integrity_ok]
            for c in cells
        ],
    )
    lines += ["", "## Rationale per pair", ""]
    for pair in matrix["pairs"]:
        lines.append(f"- `{pair['candidate']}` x `{pair['job_id']}` ({pair['expected_direction']}): {pair['rationale']}")

    report.write_text_report(REPORT_DIR / "end_to_end_report.md", lines)

    print(f"Evaluated {metrics['pairs_evaluated']} candidate x job pairs.")
    print(f"Assessment aggregation errors: {metrics['assessment_aggregation_errors']}")
    print(f"Matcher integrity errors: {metrics['matcher_integrity_errors']}")
    print(f"Reports written to {REPORT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
