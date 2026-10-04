"""Milestone 8C -- Layer B harness: candidate evidence evaluation.

Runs the REAL `extract_candidate_evidence()` against offline fixtures
rebuilt from real, previously-collected GitHub account snapshots
(`evaluation/fixtures/candidates/`), compared against hand-authored
gold (`evaluation/gold/candidates/`). No live GitHub call is made by
this script -- see `scripts/collect_pilot.py`'s sibling collection
step (ad hoc, already run) for how the fixtures themselves were
produced.

Usage:
    python scripts/evaluate_evidence.py

Exit code: 0 on a successful run (regardless of how many ranking
misses/evidence misses it finds -- those are measurements), 1 only for
a harness/fixture-level error.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from evaluation_lib import evidence_eval, report, taxonomy as tax
from evaluation_lib.loaders import EvaluationFixtureError, list_candidate_names, load_candidate_fixture, load_gold_candidate

REPORT_DIR = REPO_ROOT / "evaluation" / "reports"


def main() -> int:
    try:
        names = list_candidate_names()
        if not names:
            raise EvaluationFixtureError("no candidate fixtures found under evaluation/fixtures/candidates/")
        fixtures_and_gold = [(load_candidate_fixture(n), load_gold_candidate(n)) for n in names]
    except EvaluationFixtureError as exc:
        print(f"HARNESS ERROR: {exc}", file=sys.stderr)
        return 1

    results = evidence_eval.evaluate_candidates(fixtures_and_gold)
    metrics = evidence_eval.aggregate_metrics(results)

    json_report = {
        "corpus_version": tax.EVALUATION_CORPUS_VERSION,
        "aggregate": metrics,
        "candidates": [
            {
                "username": r.username,
                "discovered_count": r.discovered_count,
                "analyzed_count": r.analyzed_count,
                "is_complete": r.is_complete,
                "extractor_failure_count": r.extractor_failure_count,
                "ranking_verdicts": [v.__dict__ for v in r.ranking_verdicts],
                "concept_verdicts": [v.__dict__ for v in r.concept_verdicts],
                "false_positives": [v.__dict__ for v in r.false_positives],
            }
            for r in results
        ],
    }
    report.write_json_report(REPORT_DIR / "evidence_report.json", json_report)

    lines = [
        "# Candidate Evidence Evaluation Report",
        "",
        f"Corpus version: `{tax.EVALUATION_CORPUS_VERSION}`",
        f"Candidates evaluated: {metrics['candidates_evaluated']}",
        f"Ranking checks: {metrics['ranking_checks']}  |  Prediction errors: {metrics['ranking_prediction_errors']}  |  "
        f"Repository ranking misses (genuine, relevant repo excluded): {metrics['repository_ranking_misses']}",
        f"Concept checks: {metrics['concept_checks']}  |  Found: {metrics['concept_found']}  |  "
        f"Missing: {metrics['concept_missing']} (BUG={metrics['concept_missing_bugs']}, "
        f"KNOWN_SCOPE_LIMITATION={metrics['concept_missing_known_scope_limitations']})",
        f"False positives: {metrics['false_positives']}",
        f"Total extractor failures across all candidates: {metrics['total_extractor_failures']}",
        "",
        "## Per-candidate repository coverage",
        "",
    ]
    lines += report.markdown_table(
        ["username", "discovered", "analyzed", "complete"],
        [[r.username, r.discovered_count, r.analyzed_count, r.is_complete] for r in results],
    )

    lines += ["", "## Ranking verdicts", ""]
    lines += report.markdown_table(
        ["username", "repo", "predicted", "actual", "RETRIEVAL_MISS?", "notes"],
        [
            [v.username, v.repo, v.expected, v.actual, "YES" if v.is_retrieval_miss else "no", v.notes[:80]]
            for r in results for v in r.ranking_verdicts
        ],
    )

    lines += ["", "## Concept verdicts (only for analyzed repos)", ""]
    lines += report.markdown_table(
        ["username", "repo", "concept_id", "found", "tag", "classification"],
        [
            [v.username, v.repo, v.concept_id, v.found, v.tag, v.classification]
            for r in results for v in r.concept_verdicts
        ] or [["-", "-", "-", "-", "-", "-"]],
    )

    lines += ["", "## False positives (not-expected concept found)", ""]
    for r in results:
        for fp in r.false_positives:
            lines.append(f"- `{fp.username}/{fp.repo}` -> unexpectedly found {fp.concept_id!r}: {fp.notes}")
    if not any(r.false_positives for r in results):
        lines.append("(none)")

    report.write_text_report(REPORT_DIR / "evidence_report.md", lines)

    print(f"Evaluated {metrics['candidates_evaluated']} candidates.")
    print(f"Repository ranking misses: {metrics['repository_ranking_misses']}/{metrics['ranking_checks']}")
    print(f"Concept checks: found={metrics['concept_found']} missing={metrics['concept_missing']} "
          f"(bugs={metrics['concept_missing_bugs']}, known_limitations={metrics['concept_missing_known_scope_limitations']})")
    print(f"False positives: {metrics['false_positives']}")
    print(f"Reports written to {REPORT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
