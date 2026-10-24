"""Milestone 9B Phase 2 -- regression pins for the synthetic
retrieval-sensitivity fixtures (`evaluation/m9b/retrieval/`).

Unlike the Milestone 8C/8D.2 gold corpora (hand-authored expectations
about REAL GitHub accounts, where `genuinely_relevant` is deliberately
kept independent of the current implementation's measured behavior --
see `evaluation_lib/retrieval_eval.py`'s module docstring), these three
fixtures are entirely SYNTHETIC and were engineered by this milestone
specifically to produce one predetermined mechanism each (a genuine
new-evidence score flip, a crowded-out miss, and a redundant-evidence
recovery -- see each fixture's own `notes` field). There is no
separate "independent ground truth" to keep apart from "current
measured behavior" here, because the fixture WAS the ground truth by
construction. These tests are therefore plain regression pins: if a
future change to ranking, relevance scoring, matching, or assessment
ever makes the real pipeline stop reproducing the exact mechanism each
fixture was built to demonstrate, that is a genuine, reportable
regression against this milestone's own evidence base, not a fixture
error to "fix" by editing the expected values.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from evaluation_lib import retrieval_sensitivity_eval as rs_eval

RETRIEVAL_DIR = REPO_ROOT / "evaluation" / "m9b" / "retrieval"


def _load():
    candidates_doc = json.loads((RETRIEVAL_DIR / "synthetic_candidates.json").read_text(encoding="utf-8"))
    jobs_doc = json.loads((RETRIEVAL_DIR / "synthetic_jobs.json").read_text(encoding="utf-8"))
    fixtures_by_candidate = {f["candidate"]: f for f in candidates_doc["fixtures"]}
    return fixtures_by_candidate, jobs_doc["jobs"]


def test_fixture_and_job_files_load_and_cross_reference():
    fixtures_by_candidate, jobs = _load()
    assert len(fixtures_by_candidate) == 2
    assert len(jobs) == 3
    for job in jobs.values():
        assert job["candidate"] in fixtures_by_candidate
    for fixture in fixtures_by_candidate.values():
        assert fixture["synthetic"] is True, "every M9B Phase 2 fixture must self-identify as synthetic"


def test_rust_or_go_backend_case_demonstrates_a_genuine_new_evidence_score_flip():
    """The headline case M8E's own matrix could never produce: a
    repository the generic ranker excludes is recovered by job-aware
    retrieval, supplies a concept found NOWHERE else in the account, and
    that newly-SUPPORTED requirement raises alignment_score.
    """
    fixtures_by_candidate, jobs = _load()
    job = jobs["m9b_rust_or_go_backend_01"]
    case = rs_eval._evaluate_one(job, fixtures_by_candidate[job["candidate"]])

    assert case.retrieval_success is True
    assert "aaa-rust-microtool" in case.job_relevant_additions
    assert case.new_evidence_concepts == ("language.rust",)
    assert case.newly_supported_requirements == ("Proficiency in Rust or Go",)
    assert case.alignment_before == 67
    assert case.alignment_after == 100
    assert case.score_changed is True
    assert case.score_change_justified is True


def test_kotlin_preferred_case_demonstrates_a_genuine_crowded_out_miss():
    """Same candidate as the case above, but the only repository that
    could supply evidence scores the PREFERRED retrieval weight (0.5)
    while every other repository on the account scores the REQUIRED
    weight (1.0) for this job -- the fixed relevance_top_k=10 budget
    fills entirely with 1.0-scorers, so the relevant repository is never
    recovered. No score change results, and none should.
    """
    fixtures_by_candidate, jobs = _load()
    job = jobs["m9b_kotlin_preferred_01"]
    case = rs_eval._evaluate_one(job, fixtures_by_candidate[job["candidate"]])

    assert case.retrieval_success is False
    assert "kotlin-microtool" not in case.job_aware_selected
    assert case.new_evidence_concepts == ()
    assert case.newly_supported_requirements == ()
    assert case.alignment_before == case.alignment_after == 67
    assert case.score_changed is False


def test_redundant_rust_case_demonstrates_recovery_without_score_impact():
    """Retrieval succeeds (a new repository is genuinely analyzed), but
    its evidence is redundant with a concept a generically-selected
    repository already supplied -- the realistic, M8E-documented outcome
    for most real-world job-aware retrieval recoveries.
    """
    fixtures_by_candidate, jobs = _load()
    job = jobs["m9b_redundant_rust_01"]
    case = rs_eval._evaluate_one(job, fixtures_by_candidate[job["candidate"]])

    assert case.retrieval_success is True
    assert "aaa-rust-only-mini" in case.job_relevant_additions
    assert case.new_evidence_concepts == ()
    assert case.newly_supported_requirements == ()
    assert case.alignment_before == case.alignment_after == 100


def test_star_dominance_check_confirms_relevance_score_ignores_stars():
    fixtures_by_candidate, jobs = _load()
    job = jobs["m9b_rust_or_go_backend_01"]
    fixture = fixtures_by_candidate[job["candidate"]]
    result = rs_eval.star_dominance_check(
        job, fixture, popular_repo="viral-js-framework", ordinary_repo="js-service-01"
    )
    assert result["popular_repo_stars"] > 1000 * result["ordinary_repo_stars"]
    assert result["scores_equal_despite_star_gap"] is True


def test_every_case_in_the_full_evaluation_is_internally_justified():
    """No case in this synthetic suite should ever report an
    `UNEXPLAINED` justification note -- a score change with no
    corresponding newly-SUPPORTED requirement (or vice versa) would be
    an evaluation-integrity red flag (Phase 3), not merely a finding.
    """
    fixtures_by_candidate, jobs = _load()
    cases = rs_eval.evaluate_cases(jobs, fixtures_by_candidate)
    assert len(cases) == 3
    for case in cases:
        assert case.score_change_justified is True, (case.job_id, case.justification_note)
