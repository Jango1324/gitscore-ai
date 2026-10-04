"""Milestone 7C -- `gitscore.application.job_fit.analyze_job_fit()`.

Integration-style tests for the end-to-end orchestration: GitHub
username + raw pasted job description -> `JobAnalysisResult`. Every test
runs the REAL `extract_candidate_evidence()` -> `parse_job_description()`
-> `match_job()` -> `assess_job()` pipeline via a `FakeEvidenceGitHubClient`
(no network, no GitHub token) -- never mocks the domain logic itself.

`BACKEND_JD`/`ML_JD` are identical to the fixtures already used by
`tests/test_assessment_manual_examples.py` (themselves identical to
`tests/test_job_parser.py`'s own fixtures) -- duplicated verbatim here
for the same self-containment reason those files document.
"""
from __future__ import annotations

from conftest import FakeEvidenceGitHubClient, raw_repo, root_entry

from gitscore.application import JobAnalysisResult, analyze_job_fit
from gitscore.assessment import assess_job
from gitscore.github.exceptions import (
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubRequestError,
)
from gitscore.jobs import parse_job_description
from gitscore.matching import MatchStatus, match_job
from gitscore.pipeline.evidence import extract_candidate_evidence

BACKEND_JD = """Backend Software Engineer

We are a fast-growing startup revolutionizing how teams ship software.

Requirements:
- 3+ years of experience building Python backend services
- Experience with PostgreSQL
- Familiarity with Docker
- Excellent written and verbal communication

Preferred Qualifications:
- Experience with AWS
- Experience with Next.js
"""

ML_JD = """Machine Learning Engineer

About the team: we are passionate about building next-generation AI products.

Requirements:
- Expert-level Python
- Deep experience with PyTorch
- 5+ years of professional software engineering experience
- Experience with Docker or Kubernetes

Preferred Qualifications:
- Experience deploying models to AWS or Azure
- Experience mentoring junior engineers
"""

# A job description with no bullet-pointed, requirement-shaped claims at
# all -- the real parser legitimately produces zero JobRequirement
# objects from this (confirmed directly against parse_job_description();
# not an assumption about its internals).
NO_REQUIREMENTS_JD = (
    "We are a fast-growing startup revolutionizing how teams build great "
    "products together with a passionate team."
)

# Entirely non-technical claims: every one of these is NOT_ASSESSABLE
# (either NOT_OBSERVABLE, or no concept mapping at all), so the resulting
# JobAssessment has zero assessable requirements.
ZERO_ASSESSABLE_JD = """Requirements:
- 3+ years of professional experience required
- Bachelor degree in Computer Science required
- Excellent communication and leadership skills
- Must be eligible to work in the United States
"""


def _trivial_repo(name):
    """Shaped so every ranking component scores 0 -- selection becomes
    fully predictable (mirrors tests/test_pipeline_evidence.py's helper
    of the same name/purpose).
    """
    return raw_repo(name=name, description=None, language=None, stargazers_count=0)


def _backend_client_with_python_and_docker():
    return FakeEvidenceGitHubClient(
        repos=[_trivial_repo("api-service")],
        languages={"api-service": {"Python": 9000, "Shell": 1000}},
        root_contents={"api-service": [root_entry("Dockerfile")]},
    )


# ---------------------------------------------------------------------------
# A. Happy path + B/C/D/E: orchestrated result equals direct composition
# ---------------------------------------------------------------------------


def test_happy_path_produces_every_stage_output():
    client = _backend_client_with_python_and_docker()

    result = analyze_job_fit("octocat", BACKEND_JD, client=client, top_n=15)

    assert isinstance(result, JobAnalysisResult)
    assert result.candidate_profile.candidate == "octocat"
    assert result.job_profile.requirement_count == 7  # 6A's experience-claim split included
    assert result.assessment.match_analysis.requirement_count == result.job_profile.requirement_count
    assert result.assessment.alignment_score == 40


def test_result_equals_direct_component_composition():
    """B/C: the orchestrated score and required/preferred facts are
    bit-for-bit identical to calling every stage directly -- no
    orchestration-side recomputation of anything.
    """
    client_a = _backend_client_with_python_and_docker()
    client_b = _backend_client_with_python_and_docker()

    orchestrated = analyze_job_fit("octocat", BACKEND_JD, client=client_a, top_n=15)

    evidence_result = extract_candidate_evidence("octocat", client=client_b, top_n=15)
    job_profile = parse_job_description(BACKEND_JD)
    match_analysis = match_job(evidence_result.profile, job_profile)
    direct_assessment = assess_job(match_analysis)

    assert orchestrated.assessment.alignment_score == direct_assessment.alignment_score
    assert orchestrated.assessment.required == direct_assessment.required
    assert orchestrated.assessment.preferred == direct_assessment.preferred
    assert orchestrated.assessment == direct_assessment


def test_supporting_evidence_survives_to_the_result():
    """D: supporting Evidence for a SUPPORTED requirement is reachable
    off the final result, unmodified, all the way from extraction.
    """
    client = _backend_client_with_python_and_docker()

    result = analyze_job_fit("octocat", BACKEND_JD, client=client, top_n=15)

    docker_match = next(
        m for m in result.assessment.supported_matches() if m.matched_concept_ids == ("infra.docker",)
    )
    assert len(docker_match.supporting_evidence) == 1
    evidence_item = docker_match.supporting_evidence[0]
    assert evidence_item.repository.name == "api-service"
    assert evidence_item in result.candidate_profile.evidence


def test_repository_coverage_survives_orchestration():
    """E: coverage facts on the result match what extraction actually did,
    with no re-derived percentage anywhere.
    """
    repos = [_trivial_repo(f"repo-{i:02d}") for i in range(20)]
    client = FakeEvidenceGitHubClient(repos=repos)

    result = analyze_job_fit("octocat", BACKEND_JD, client=client, top_n=15)

    coverage = result.candidate_profile.coverage
    assert coverage.discovered_count == 20
    assert coverage.analyzed_count == 15
    assert coverage is result.assessment.match_analysis.coverage


# ---------------------------------------------------------------------------
# F/G: OR semantics and NOT_ASSESSABLE survive orchestration unchanged
# ---------------------------------------------------------------------------


def test_or_group_semantics_survive_orchestration():
    client = FakeEvidenceGitHubClient(
        repos=[_trivial_repo("training-repo")],
        languages={"training-repo": {"Python": 9000, "Shell": 1000}},
        root_contents={"training-repo": [root_entry("Dockerfile")]},
    )

    result = analyze_job_fit("octocat", ML_JD, client=client, top_n=15)

    or_group_matches = [
        m for m in result.assessment.match_analysis.requirement_matches if m.requirement.is_alternative_group
    ]
    assert len(or_group_matches) == 2
    docker_or_k8s = next(m for m in or_group_matches if m.requirement.necessity.value == "required")
    assert docker_or_k8s.status == MatchStatus.SUPPORTED
    # Supported via Docker alone -- counted once, not once per alternative.
    assert sum(1 for m in result.assessment.supported_matches() if m.requirement.is_alternative_group) == 1


def test_not_assessable_requirements_survive_orchestration():
    client = _backend_client_with_python_and_docker()

    result = analyze_job_fit("octocat", BACKEND_JD, client=client, top_n=15)

    not_assessable_texts = {m.requirement.original_text for m in result.assessment.not_assessable_matches()}
    assert any("communication" in t.lower() for t in not_assessable_texts)
    assert any("experience" in t.lower() for t in not_assessable_texts)


# ---------------------------------------------------------------------------
# H/I: input validation -- blank username / blank job description
# ---------------------------------------------------------------------------


def test_blank_username_raises_value_error_before_any_network_call():
    class ExplodingClient:
        def get_repositories(self, username):
            raise AssertionError("must not be called for a blank username")

    try:
        analyze_job_fit("   ", BACKEND_JD, client=ExplodingClient())
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "username" in str(exc)


def test_blank_job_description_raises_value_error_before_any_network_call():
    class ExplodingClient:
        def get_repositories(self, username):
            raise AssertionError("must not be called for a blank job description")

    try:
        analyze_job_fit("octocat", "   ", client=ExplodingClient())
        assert False, "expected ValueError"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# J/K: GitHub-side failures propagate unchanged, never swallowed
# ---------------------------------------------------------------------------


def test_github_user_not_found_propagates():
    client = FakeEvidenceGitHubClient(repos_exc=GitHubNotFoundError("no such user"))

    try:
        analyze_job_fit("ghost-user-xyz", BACKEND_JD, client=client)
        assert False, "expected GitHubNotFoundError"
    except GitHubNotFoundError:
        pass


def test_github_rate_limit_propagates():
    client = FakeEvidenceGitHubClient(repos_exc=GitHubRateLimitError("rate limited"))

    try:
        analyze_job_fit("octocat", BACKEND_JD, client=client)
        assert False, "expected GitHubRateLimitError"
    except GitHubRateLimitError:
        pass


def test_github_request_error_propagates():
    client = FakeEvidenceGitHubClient(
        repos_exc=GitHubRequestError("network failure", status_code=None)
    )

    try:
        analyze_job_fit("octocat", BACKEND_JD, client=client)
        assert False, "expected GitHubRequestError"
    except GitHubRequestError:
        pass


# ---------------------------------------------------------------------------
# G/K/J/L: "completed with nothing to report" vs. "could not complete"
# ---------------------------------------------------------------------------


def test_zero_repositories_still_produces_a_successful_result():
    client = FakeEvidenceGitHubClient(repos=[])

    result = analyze_job_fit("brand-new-account", BACKEND_JD, client=client, top_n=15)

    assert result.candidate_profile.coverage.discovered_count == 0
    assert result.candidate_profile.coverage.analyzed_count == 0
    assert result.candidate_profile.evidence == ()
    # Every technical requirement is assessable (NOT_OBSERVED) even with
    # zero evidence -- a real, non-None score, not a failure.
    assert result.assessment.assessable_count == 5
    assert result.assessment.alignment_score == 0


def test_candidate_with_zero_matching_evidence_scores_zero_not_none():
    client = FakeEvidenceGitHubClient(repos=[_trivial_repo("unrelated-repo")])

    result = analyze_job_fit("octocat", BACKEND_JD, client=client, top_n=15)

    assert result.candidate_profile.evidence == ()
    assert result.assessment.assessable_count == 5
    assert result.assessment.alignment_score == 0
    assert result.assessment.required.supported == 0


def test_job_description_with_zero_requirements_produces_none_score():
    client = FakeEvidenceGitHubClient(repos=[_trivial_repo("api-service")])

    result = analyze_job_fit("octocat", NO_REQUIREMENTS_JD, client=client, top_n=15)

    assert result.job_profile.requirement_count == 0
    assert result.assessment.assessable_count == 0
    assert result.assessment.alignment_score is None
    assert result.assessment.required is None
    assert result.assessment.preferred is None


def test_zero_assessable_requirements_produces_none_score_not_zero():
    """L: a posting whose every requirement is NOT_ASSESSABLE must report
    `alignment_score is None` -- a materially different fact from `0`
    (which would claim GitHub evidence was checked and found lacking).
    """
    client = _backend_client_with_python_and_docker()

    result = analyze_job_fit("octocat", ZERO_ASSESSABLE_JD, client=client, top_n=15)

    assert result.job_profile.requirement_count > 0
    assert result.assessment.assessable_count == 0
    assert result.assessment.alignment_score is None


# ---------------------------------------------------------------------------
# I: partial per-repository extraction failure is surfaced, not fatal
# ---------------------------------------------------------------------------


def test_partial_repository_extraction_failure_does_not_abort_analysis():
    client = FakeEvidenceGitHubClient(
        repos=[_trivial_repo("flaky")],
        languages_exc_for={"flaky": GitHubRequestError("boom", status_code=500)},
        readme={"flaky": ("Uses PostgreSQL.", "README.md")},
    )

    result = analyze_job_fit("octocat", BACKEND_JD, client=client, top_n=15)

    assert len(result.extractor_failures) == 1
    assert result.extractor_failures[0].source == "languages"
    assert "flaky" in {r.name for r in result.candidate_profile.coverage.partially_analyzed}
    # README evidence still made it through despite the language failure.
    assert any(item.concept_id == "database.postgresql" for item in result.candidate_profile.evidence)
    assert result.assessment.alignment_score is not None


# ---------------------------------------------------------------------------
# P: determinism of the deterministic stages given identical GitHub data
# ---------------------------------------------------------------------------


def test_identical_fake_github_responses_produce_identical_results():
    client_a = _backend_client_with_python_and_docker()
    client_b = _backend_client_with_python_and_docker()

    result_a = analyze_job_fit("octocat", BACKEND_JD, client=client_a, top_n=15)
    result_b = analyze_job_fit("octocat", BACKEND_JD, client=client_b, top_n=15)

    assert result_a.candidate_profile == result_b.candidate_profile
    assert result_a.job_profile == result_b.job_profile
    assert result_a.assessment == result_b.assessment


# ---------------------------------------------------------------------------
# Q: each stage runs exactly once -- no rematch/reassess to build fields
# ---------------------------------------------------------------------------


def test_each_stage_runs_exactly_once():
    call_counts = {"extract": 0, "parse": 0, "match": 0, "assess": 0}

    import gitscore.application.job_fit as job_fit_module

    real_extract = job_fit_module.extract_candidate_evidence
    real_parse = job_fit_module.parse_job_description
    real_match = job_fit_module.match_job
    real_assess = job_fit_module.assess_job

    def counting_extract(*args, **kwargs):
        call_counts["extract"] += 1
        return real_extract(*args, **kwargs)

    def counting_parse(*args, **kwargs):
        call_counts["parse"] += 1
        return real_parse(*args, **kwargs)

    def counting_match(*args, **kwargs):
        call_counts["match"] += 1
        return real_match(*args, **kwargs)

    def counting_assess(*args, **kwargs):
        call_counts["assess"] += 1
        return real_assess(*args, **kwargs)

    job_fit_module.extract_candidate_evidence = counting_extract
    job_fit_module.parse_job_description = counting_parse
    job_fit_module.match_job = counting_match
    job_fit_module.assess_job = counting_assess
    try:
        client = _backend_client_with_python_and_docker()
        job_fit_module.analyze_job_fit("octocat", BACKEND_JD, client=client, top_n=15)
    finally:
        job_fit_module.extract_candidate_evidence = real_extract
        job_fit_module.parse_job_description = real_parse
        job_fit_module.match_job = real_match
        job_fit_module.assess_job = real_assess

    assert call_counts == {"extract": 1, "parse": 1, "match": 1, "assess": 1}
