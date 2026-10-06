"""Milestone 8C -- tests for the EVALUATOR tooling itself
(`scripts/evaluation_lib/`), not for whether GitScore currently passes
its own benchmark.

These tests must stay green regardless of how GitScore's real pipeline
behaves today -- they pin the classification ALGORITHM (given a known
gold/actual pair, does it produce the documented verdict), fixture
loading/error handling, and determinism. They never assert "GitScore
scored X" the way `tests/test_assessment_manual_examples.py` etc. do
for production code -- see Milestone 8C Part 19/25.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pytest

from evaluation_lib import parser_eval, taxonomy as tax
from evaluation_lib.loaders import (
    EvaluationFixtureError,
    build_fake_client,
    list_candidate_names,
    list_job_ids,
    load_gold_candidate,
    load_gold_job,
    load_job,
    load_job_and_gold,
)


# ---------------------------------------------------------------------------
# Loaders: real corpus smoke-loads + error handling on bad input
# ---------------------------------------------------------------------------


def test_real_corpus_has_at_least_twelve_jobs():
    job_ids = list_job_ids()
    assert 12 <= len(job_ids) <= 20


def test_every_real_job_and_gold_file_loads_and_cross_references_correctly():
    for job_id in list_job_ids():
        job, gold = load_job_and_gold(job_id)
        assert job["job_id"] == job_id == gold["job_id"]
        assert job["raw_text"].strip()
        assert len(gold["expected_requirements"]) > 0


def test_real_candidate_fixtures_and_gold_exist():
    names = list_candidate_names()
    assert 4 <= len(names) <= 8
    for name in names:
        gold = load_gold_candidate(name)
        assert gold["targets"]


def test_missing_job_raises_fixture_error():
    with pytest.raises(EvaluationFixtureError):
        load_job("this_job_id_does_not_exist")


def test_missing_gold_candidate_raises_fixture_error():
    with pytest.raises(EvaluationFixtureError):
        load_gold_candidate("this_candidate_does_not_exist")


def test_gold_job_id_mismatch_is_rejected(tmp_path, monkeypatch):
    import evaluation_lib.loaders as loaders_module

    monkeypatch.setattr(loaders_module, "GOLD_JOBS_DIR", tmp_path)
    (tmp_path / "real_id.json").write_text(
        '{"job_id": "wrong_id", "expected_requirements": []}', encoding="utf-8"
    )
    with pytest.raises(EvaluationFixtureError):
        load_gold_job("real_id")


def test_malformed_json_raises_fixture_error(tmp_path, monkeypatch):
    import evaluation_lib.loaders as loaders_module

    monkeypatch.setattr(loaders_module, "GOLD_JOBS_DIR", tmp_path)
    (tmp_path / "broken.json").write_text("{not valid json", encoding="utf-8")
    with pytest.raises(EvaluationFixtureError):
        load_gold_job("broken")


def test_build_fake_client_shapes_match_fake_evidence_github_client_contract():
    fixture = {
        "repos_raw": [{"name": "repo-a", "description": None}],
        "selected": {
            "repo-a": {
                "languages": {"Python": 1000},
                "readme": ["hello world", "README.md"],
                "root_contents": [{"name": "requirements.txt", "path": "requirements.txt", "type": "file"}],
                "files": {"requirements.txt": "torch==2.5\n"},
            }
        },
    }
    client = build_fake_client(fixture)
    assert client.get_repositories("whoever") == fixture["repos_raw"]
    assert client.get_repository_languages("owner", "repo-a") == {"Python": 1000}
    assert client.get_repository_readme_with_path("owner", "repo-a") == ("hello world", "README.md")
    assert client.get_repository_root_contents("owner", "repo-a")[0]["name"] == "requirements.txt"
    assert client.get_repository_file("owner", "repo-a", "requirements.txt") == "torch==2.5\n"
    # Absence is a plain miss, never a crash.
    assert client.get_repository_readme_with_path("owner", "unknown-repo") is None
    assert client.get_repository_languages("owner", "unknown-repo") == {}


# ---------------------------------------------------------------------------
# parser_eval classification algorithm -- controlled synthetic inputs
# ---------------------------------------------------------------------------


def _tech_gold(claim_text, necessity, concept_id, observability="strongly_observable"):
    return {
        "claim_text": claim_text, "necessity": necessity, "facet": "technical",
        "concept_id": concept_id, "github_observability": observability, "notes": "",
    }


def _alt_gold(claim_text, necessity, concept_ids, observability="strongly_observable"):
    return {
        "claim_text": claim_text, "necessity": necessity, "facet": "alternative",
        "alternative_concept_ids": sorted(concept_ids), "github_observability": observability, "notes": "",
    }


def _nontech_gold(claim_text, necessity, category, observability):
    return {
        "claim_text": claim_text, "necessity": necessity, "facet": "non_technical",
        "category": category, "github_observability": observability, "notes": "",
    }


def _job(job_id, raw_text, title=None):
    return {"job_id": job_id, "role_family": "test", "title": title, "raw_text": raw_text}


def test_correct_technical_requirement_is_classified_correct():
    raw = "Requirements:\n- Experience with Docker\n"
    job = _job("t1", raw)
    gold = {"job_id": "t1", "expected_requirements": [
        _tech_gold("Experience with Docker", "required", "infra.docker"),
    ]}
    result = parser_eval.evaluate_job(job, gold)
    assert len(result.verdicts) == 1
    assert result.verdicts[0].status == tax.CORRECT
    assert result.spurious == []


def test_concept_never_mentioned_is_classified_missing():
    raw = "Requirements:\n- Experience with Docker\n"
    job = _job("t2", raw)
    gold = {"job_id": "t2", "expected_requirements": [
        _tech_gold("Experience with Docker", "required", "cloud.aws"),  # AWS never mentioned
    ]}
    result = parser_eval.evaluate_job(job, gold)
    assert result.verdicts[0].status == tax.MISSING


def test_wrong_necessity_is_flagged_but_concept_still_recognized():
    raw = "Preferred Qualifications:\n- Experience with Docker\n"
    job = _job("t3", raw)
    # Gold expects REQUIRED, but this bullet is under "Preferred Qualifications".
    gold = {"job_id": "t3", "expected_requirements": [
        _tech_gold("Experience with Docker", "required", "infra.docker"),
    ]}
    result = parser_eval.evaluate_job(job, gold)
    assert result.verdicts[0].status == tax.PARTIALLY_CORRECT
    assert tax.WRONG_NECESSITY in result.verdicts[0].tags


def test_alternative_group_exact_match_is_correct():
    raw = "Requirements:\n- Experience with Python or Rust\n"
    job = _job("t4", raw)
    gold = {"job_id": "t4", "expected_requirements": [
        _alt_gold("Experience with Python or Rust", "required", ["language.python", "language.rust"]),
    ]}
    result = parser_eval.evaluate_job(job, gold)
    assert result.verdicts[0].status == tax.CORRECT


def test_alternative_group_wrong_id_set_is_wrong_alternative_structure():
    raw = "Requirements:\n- Experience with Python or Rust\n"
    job = _job("t5", raw)
    # Deliberately wrong expected ids (Go instead of Rust) to exercise the mismatch branch.
    gold = {"job_id": "t5", "expected_requirements": [
        _alt_gold("Experience with Python or Rust", "required", ["language.go", "language.python"]),
    ]}
    result = parser_eval.evaluate_job(job, gold)
    assert result.verdicts[0].status == tax.WRONG_ALTERNATIVE_STRUCTURE


def test_unclaimed_actual_requirement_is_spurious():
    raw = "Requirements:\n- Experience with Docker and Python\n"
    job = _job("t6", raw)
    # Gold only claims Docker -- the real Python requirement under the
    # same claim_text is never accounted for.
    gold = {"job_id": "t6", "expected_requirements": [
        _tech_gold("Experience with Docker and Python", "required", "infra.docker"),
    ]}
    result = parser_eval.evaluate_job(job, gold)
    assert result.verdicts[0].status == tax.CORRECT
    assert len(result.spurious) == 1
    assert result.spurious[0].concept_id == "language.python"


def test_non_technical_category_match_is_correct():
    raw = "Requirements:\n- Bachelor's degree in Computer Science\n"
    job = _job("t7", raw)
    gold = {"job_id": "t7", "expected_requirements": [
        _nontech_gold("Bachelor's degree in Computer Science", "required", "education", "not_observable"),
    ]}
    result = parser_eval.evaluate_job(job, gold)
    assert result.verdicts[0].status == tax.CORRECT


def test_aggregate_metrics_counts_match_individual_verdicts():
    # Milestone 8D.1: a deliberately synthetic, guaranteed-unregistered
    # term (Kubernetes -- the real-world example this test used before --
    # is now a registered concept) so this test keeps exercising genuine
    # MISSING-classification behavior.
    raw = "Requirements:\n- Experience with Docker\n- Experience with SomeUnknownOrchestrator\n"
    job = _job("t8", raw)
    gold = {"job_id": "t8", "expected_requirements": [
        _tech_gold("Experience with Docker", "required", "infra.docker"),
        _tech_gold("Experience with SomeUnknownOrchestrator", "required", "unresolved:someunknownorchestrator"),
    ]}
    results = [parser_eval.evaluate_job(job, gold)]
    metrics = parser_eval.aggregate_metrics(results)
    assert metrics["total_expected_requirements"] == 2
    assert metrics["status_counts"][tax.CORRECT] == 1
    assert metrics["status_counts"][tax.MISSING] == 1
    assert metrics["missed_concepts"]["unresolved:someunknownorchestrator"] == 1


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_evaluate_job_is_deterministic_across_repeated_runs():
    raw = "Requirements:\n- Experience with Docker or Kubernetes\n- 3+ years of Python experience\n"
    job = _job("t9", raw)
    gold = {"job_id": "t9", "expected_requirements": [
        _alt_gold("Experience with Docker or Kubernetes", "required", ["infra.docker", "infra.kubernetes"]),
        _tech_gold("3+ years of Python experience", "required", "language.python"),
        _nontech_gold("3+ years of Python experience", "required", "experience", "not_observable"),
    ]}
    result_a = parser_eval.evaluate_job(job, gold)
    result_b = parser_eval.evaluate_job(job, gold)
    statuses_a = [(v.claim_text, v.facet, v.status, v.tags) for v in result_a.verdicts]
    statuses_b = [(v.claim_text, v.facet, v.status, v.tags) for v in result_b.verdicts]
    assert statuses_a == statuses_b


# ---------------------------------------------------------------------------
# end_to_end_eval pure helpers
# ---------------------------------------------------------------------------


def test_recompute_alignment_matches_assessment_formula():
    from evaluation_lib.end_to_end_eval import _recompute_alignment

    assert _recompute_alignment(0, 0) is None
    assert _recompute_alignment(2, 4) == 50
    assert _recompute_alignment(5, 8) == 63  # half-up: 62.5 -> 63


def test_matcher_integrity_rejects_out_of_scope_matched_ids():
    from gitscore.evidence.models import Evidence, RepositoryIdentity
    from gitscore.evidence.types import ConfidenceLevel, EvidenceType
    from gitscore.jobs.models import JobRequirement
    from gitscore.jobs.types import GithubObservability, Importance, Necessity
    from gitscore.matching.models import JobMatchAnalysis, RequirementMatch
    from gitscore.matching.types import MatchStatus
    from gitscore.evidence.profile import RepositoryAnalysisCoverage

    from evaluation_lib.end_to_end_eval import _matcher_integrity_ok

    requirement = JobRequirement(
        original_text="Experience with Docker", necessity=Necessity.REQUIRED,
        importance=Importance.MEDIUM, github_observability=GithubObservability.STRONGLY_OBSERVABLE,
        concept_id="infra.docker",
    )
    evidence = (
        Evidence(
            repository=RepositoryIdentity("owner", "repo"), evidence_type=EvidenceType.DOCKER,
            raw_observation="x", concept_id="infra.docker", confidence=ConfidenceLevel.STRONG,
            extractor_version="test@1",
        ),
    )
    valid_match = RequirementMatch(
        requirement=requirement, status=MatchStatus.SUPPORTED,
        matched_concept_ids=("infra.docker",), supporting_evidence=evidence,
    )
    analysis = JobMatchAnalysis(
        candidate="c", job_title=None, job_company=None, requirement_matches=(valid_match,),
        coverage=RepositoryAnalysisCoverage(discovered=(), analyzed=()), matcher_version="test:v1",
    )
    assert _matcher_integrity_ok(analysis) is True
