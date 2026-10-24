"""Milestone 9B Phase 3 -- tests for the evaluation-integrity safeguard
tooling (`scripts/check_evaluation_staleness.py`) and a handful of
structural guards against the specific integrity failure modes the
milestone brief names (gold revised after seeing output, a frozen
corpus edited in place, a cached candidate-only profile reused under a
job-aware label, requirements dropped silently before assessment).

These tests pin the SAFEGUARD TOOLING's own correctness -- not whether
any particular committed report is currently fresh or stale (that is a
measurement `check_evaluation_staleness.py` reports, never a test
assertion; a "STALE" finding is expected and already disclosed for at
least one committed report as of this milestone -- see
docs/evaluation/MILESTONE_9B_EVALUATION_INTEGRITY.md Section 10).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import check_evaluation_staleness as staleness


def test_diff_dict_reports_no_diffs_for_identical_dicts():
    assert staleness._diff_dict({"a": 1, "b": 2}, {"a": 1, "b": 2}) == {}


def test_diff_dict_reports_exactly_the_changed_keys():
    fresh = {"a": 1, "b": 2, "c": 3}
    committed = {"a": 1, "b": 99, "d": 4}
    diffs = staleness._diff_dict(fresh, committed)
    assert set(diffs) == {"b", "c", "d"}
    assert diffs["b"] == {"fresh": 2, "committed": 99}
    assert diffs["c"] == {"fresh": 3, "committed": None}
    assert diffs["d"] == {"fresh": None, "committed": 4}


def test_check_parser_on_frozen_8c_v1_runs_without_raising():
    """Does not assert FRESH vs STALE (that is a measurement) -- only
    that the read-only recompute-and-diff mechanism itself runs cleanly
    against the real, frozen corpus without ever writing a file.
    """
    from evaluation_lib.loaders import GOLD_JOBS_DIR

    before = (REPO_ROOT / "evaluation" / "reports" / "parser_report.json").read_text(encoding="utf-8")
    result = staleness.check_parser("8c:v1", "parser_report.json", GOLD_JOBS_DIR)
    after = (REPO_ROOT / "evaluation" / "reports" / "parser_report.json").read_text(encoding="utf-8")

    assert result["status"] in ("FRESH", "STALE", "MISSING")
    assert before == after, "check_parser must never write to the committed report file"


def test_check_evaluation_staleness_main_never_writes_to_any_committed_report(tmp_path, monkeypatch):
    """A broad, repo-wide guard: running the full staleness checker must
    not modify a single byte under evaluation/reports/ -- it is a
    read-only diagnostic by design (module docstring).
    """
    report_dir = REPO_ROOT / "evaluation" / "reports"
    before = {p: p.read_bytes() for p in report_dir.glob("*.json")}

    exit_code = staleness.main()

    after = {p: p.read_bytes() for p in report_dir.glob("*.json")}
    assert exit_code == 0
    assert before == after


# ---------------------------------------------------------------------------
# Structural integrity guards named directly in the Milestone 9B brief
# ---------------------------------------------------------------------------


def test_frozen_8c_gold_directories_are_not_imported_by_any_m9b_module():
    """Milestone 9B's own new corpus/evaluator must be purely additive --
    it must never import the frozen-gold-directory CONSTANTS
    `GOLD_JOBS_DIR(_V1_1)`/`GOLD_CANDIDATES_DIR(_V1_1)` from
    `evaluation_lib.loaders` (the actual symbols every 8c:v1/8c:v1.1
    harness uses to reach `evaluation/gold/`/`evaluation/gold_v1_1/`).
    Checked against the real Python identifiers, not docstring prose
    that merely DESCRIBES those directories (which is expected and
    appears throughout this milestone's own documentation).
    """
    m9b_modules = [
        SCRIPTS_DIR / "evaluation_lib" / "preservation_eval.py",
        SCRIPTS_DIR / "evaluation_lib" / "retrieval_sensitivity_eval.py",
        SCRIPTS_DIR / "evaluate_m9b_preservation.py",
        SCRIPTS_DIR / "evaluate_m9b_retrieval_sensitivity.py",
    ]
    forbidden_identifiers = ("GOLD_JOBS_DIR", "GOLD_JOBS_DIR_V1_1", "GOLD_CANDIDATES_DIR", "GOLD_CANDIDATES_DIR_V1_1")
    for module_path in m9b_modules:
        text = module_path.read_text(encoding="utf-8")
        for identifier in forbidden_identifiers:
            assert identifier not in text, (module_path, identifier)


def test_m9b_corpus_and_retrieval_fixtures_are_separate_files_from_frozen_gold():
    m9b_dir = REPO_ROOT / "evaluation" / "m9b"
    frozen_dirs = {REPO_ROOT / "evaluation" / "gold", REPO_ROOT / "evaluation" / "gold_v1_1"}
    for path in m9b_dir.rglob("*.json"):
        assert not any(str(path).startswith(str(frozen)) for frozen in frozen_dirs)


def test_retrieval_fixtures_keep_an_independent_judgment_field_separate_from_the_regression_pin():
    """Mirrors the Milestone 8D.2 `genuinely_relevant` vs `expected_analyzed`
    separation this project already established: every M9B synthetic
    fixture must document ITS OWN intended mechanism (`test_intent`,
    authored at design time) separately from whatever the evaluator
    measures at run time -- never only the latter.
    """
    import json

    jobs_doc = json.loads((REPO_ROOT / "evaluation" / "m9b" / "retrieval" / "synthetic_jobs.json").read_text(encoding="utf-8"))
    for job in jobs_doc["jobs"].values():
        assert job.get("test_intent"), f"{job['job_id']} is missing its design-time test_intent"
