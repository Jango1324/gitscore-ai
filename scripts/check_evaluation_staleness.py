"""Milestone 9B Phase 3 -- evaluation-integrity safeguard: committed
report staleness checker.

M8D.3 and M8E/9A each found, by ad hoc manual inspection, that a
committed `evaluation/reports/*.json` file had drifted from what its own
generating script would currently produce (`evidence_report.json` after
8D.3's README fix; `end_to_end_report.json`'s `karpathy x frontend_01`
cell after the same fix) -- each time, this was the EXPECTED, disclosed
kind of staleness (a frozen `8c:v1` benchmark intentionally left
un-regenerated per the project's own reporting discipline), but nothing
previously made that check repeatable or automatic. This script
generalizes the exact manual process those two milestones used (recompute
fresh in memory, diff against the committed file, never overwrite it) into
one reusable, read-only tool.

Deliberately read-only: every comparison below recomputes metrics THROUGH
THE SAME `evaluation_lib` aggregation functions each `scripts/evaluate_*.py`
already calls, entirely in memory, and reads the already-committed JSON
report with plain `json.loads` -- it never calls any `evaluate_*.py`
script's own `main()` (which would overwrite the committed file in place)
and never writes anything itself. A "stale" finding here is not
necessarily a bug -- it may be exactly the intentional, disclosed kind of
staleness this project has already documented twice -- but it should
never go unnoticed again.

Usage:
    python scripts/check_evaluation_staleness.py

Exit code: 0 always (this is a reporting tool, not a test gate -- staleness
findings are measurements for a human to triage, mirroring every other
scripts/evaluate_*.py's own "measurements, not assertions" policy). Use
`tests/test_m9b_evaluation_integrity.py` for a pytest-gated subset if a
hard CI check is ever wanted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from evaluation_lib import end_to_end_eval, evidence_eval, parser_eval, retrieval_eval
from evaluation_lib.loaders import (
    GOLD_CANDIDATES_DIR,
    GOLD_CANDIDATES_DIR_V1_1,
    GOLD_JOBS_DIR,
    GOLD_JOBS_DIR_V1_1,
    build_fake_client,
    list_candidate_names,
    list_job_ids,
    load_candidate_fixture,
    load_gold_candidate,
    load_gold_job,
    load_job,
    load_retrieval_cases,
)

REPORT_DIR = REPO_ROOT / "evaluation" / "reports"
MATRIX_PATH = REPO_ROOT / "evaluation" / "gold" / "matrix.json"


def _read_committed(name: str) -> dict | None:
    path = REPORT_DIR / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _diff_dict(fresh: dict, committed: dict) -> dict:
    keys = set(fresh) | set(committed)
    diffs = {}
    for key in sorted(keys):
        if fresh.get(key) != committed.get(key):
            diffs[key] = {"fresh": fresh.get(key), "committed": committed.get(key)}
    return diffs


def check_parser(corpus_version: str, report_name: str, gold_jobs_dir) -> dict:
    job_ids = list_job_ids()
    jobs_and_gold = [(load_job(j), load_gold_job(j, gold_jobs_dir=gold_jobs_dir)) for j in job_ids]
    fresh = parser_eval.aggregate_metrics(parser_eval.evaluate_jobs(jobs_and_gold))
    committed = _read_committed(report_name)
    if committed is None:
        return {"report": report_name, "status": "MISSING", "diffs": {}}
    diffs = _diff_dict(fresh, committed.get("aggregate", {}))
    return {"report": report_name, "status": "STALE" if diffs else "FRESH", "diffs": diffs}


def check_evidence(report_name: str, gold_candidates_dir) -> dict:
    names = list_candidate_names()
    fixtures_and_gold = [
        (load_candidate_fixture(n), load_gold_candidate(n, gold_candidates_dir=gold_candidates_dir)) for n in names
    ]
    fresh = evidence_eval.aggregate_metrics(evidence_eval.evaluate_candidates(fixtures_and_gold))
    committed = _read_committed(report_name)
    if committed is None:
        return {"report": report_name, "status": "MISSING", "diffs": {}}
    diffs = _diff_dict(fresh, committed.get("aggregate", {}))
    return {"report": report_name, "status": "STALE" if diffs else "FRESH", "diffs": diffs}


def check_retrieval() -> dict:
    gold = load_retrieval_cases()
    candidate_names = list_candidate_names()
    fixtures = {}
    for case in gold["cases"]:
        name = case["candidate"]
        match = next((n for n in candidate_names if n.lower() == name.lower()), None)
        if match:
            fixtures[name] = load_candidate_fixture(match)
    job_ids = list_job_ids()
    jobs = {j: load_job(j) for j in job_ids}

    case_results = retrieval_eval.evaluate_cases(gold["cases"], fixtures, jobs)
    fresh = retrieval_eval.aggregate_metrics(case_results)
    committed = _read_committed("retrieval_report.json")
    if committed is None:
        return {"report": "retrieval_report.json", "status": "MISSING", "diffs": {}}
    diffs = _diff_dict(fresh, committed.get("aggregate", {}))
    return {"report": "retrieval_report.json", "status": "STALE" if diffs else "FRESH", "diffs": diffs}


def check_end_to_end() -> dict:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    candidate_names = list_candidate_names()
    fixtures = {}
    for pair in matrix["pairs"]:
        name = pair["candidate"]
        match = next((n for n in candidate_names if n.lower() == name.lower()), None)
        if match:
            fixtures[name] = load_candidate_fixture(match)
    jobs = {j: load_job(j) for j in list_job_ids()}

    candidate_profiles = end_to_end_eval.build_candidate_profiles(fixtures)
    cells = end_to_end_eval.evaluate_matrix(matrix, candidate_profiles, jobs)
    fresh_aggregate = end_to_end_eval.aggregate_metrics(cells)

    committed = _read_committed("end_to_end_report.json")
    if committed is None:
        return {"report": "end_to_end_report.json", "status": "MISSING", "diffs": {}}

    diffs = _diff_dict(fresh_aggregate, committed.get("aggregate", {}))

    # The known-sensitive per-cell check (8D.3/9A both found drift HERE,
    # not in the aggregate counts) -- compare each (candidate, job_id)
    # cell's alignment_score/required/preferred individually, never only
    # the aggregate error counts, which can stay zero even while
    # individual scores move.
    committed_cells = {(c["candidate"], c["job_id"]): c for c in committed.get("cells", [])}
    cell_diffs = []
    for cell in cells:
        key = (cell.candidate, cell.job_id)
        committed_cell = committed_cells.get(key)
        if committed_cell is None:
            cell_diffs.append({"cell": key, "issue": "missing from committed report"})
            continue
        fresh_triple = (cell.alignment_score, cell.required, cell.preferred)
        committed_triple = (
            committed_cell.get("alignment_score"),
            tuple(committed_cell["required"]) if committed_cell.get("required") else None,
            tuple(committed_cell["preferred"]) if committed_cell.get("preferred") else None,
        )
        if fresh_triple != committed_triple:
            cell_diffs.append({"cell": key, "fresh": fresh_triple, "committed": committed_triple})

    status = "STALE" if (diffs or cell_diffs) else "FRESH"
    return {"report": "end_to_end_report.json", "status": status, "diffs": diffs, "cell_diffs": cell_diffs}


def main() -> int:
    results = [
        check_parser(tax_corpus, name, gold_dir)
        for tax_corpus, name, gold_dir in [
            ("8c:v1", "parser_report.json", GOLD_JOBS_DIR),
            ("8c:v1.1", "parser_report_v1_1.json", GOLD_JOBS_DIR_V1_1),
        ]
    ]
    results += [
        check_evidence("evidence_report.json", GOLD_CANDIDATES_DIR),
        check_evidence("evidence_report_v1_1.json", GOLD_CANDIDATES_DIR_V1_1),
        check_retrieval(),
        check_end_to_end(),
    ]

    print(f"{'report':<28}{'status':<10}diffs")
    for r in results:
        extra = len(r["diffs"]) + len(r.get("cell_diffs", []))
        print(f"{r['report']:<28}{r['status']:<10}{extra}")
        for key, diff in r["diffs"].items():
            print(f"    aggregate[{key}]: committed={diff['committed']!r} fresh={diff['fresh']!r}")
        for cell_diff in r.get("cell_diffs", []):
            print(f"    cell {cell_diff.get('cell')}: {cell_diff}")

    stale = [r for r in results if r["status"] == "STALE"]
    if stale:
        print()
        print(f"{len(stale)} committed report(s) disagree with a fresh recompute under current code.")
        print("This is NOT automatically a bug -- cross-check against docs/CHANGELOG_DEV.md and the most")
        print("recent milestone's evaluation report before concluding anything was broken; frozen 8c:v1")
        print("reports are sometimes intentionally left un-regenerated (see MILESTONE_8D3/8E/9A docs).")
    else:
        print()
        print("All checked committed reports match a fresh recompute under current code.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
