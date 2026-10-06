"""Milestone 7A Part 18 -- manual validation of the requirement matcher
against the four real, hand-written job postings already used for
Milestone 6B/6B.1's manual parser validation (`tests/test_job_parser.py`
-- BACKEND_JD, ROBOTICS_JD, ML_JD, DATA_ENGINEERING_JD), each run through
the REAL `parse_job_description()` (not hand-built requirements) and
matched against several LOCAL, deliberately-mixed candidate evidence
profiles.

No real GitHub API call anywhere -- every `Evidence` item is
hand-constructed, exactly like every other candidate-evidence test in
this suite. No score is computed or asserted anywhere in this file: the
only things inspected are `MatchStatus` values, `matched_concept_ids`,
and `supporting_evidence` provenance.
"""
from gitscore.evidence import ConfidenceLevel, Evidence, EvidenceType, RepositoryIdentity, build_candidate_evidence_profile
from gitscore.jobs import GithubObservability, parse_job_description
from gitscore.matching import JobMatchAnalysis, MatchStatus, match_job

# Identical fixture text to tests/test_job_parser.py's BACKEND_JD/
# ROBOTICS_JD/ML_JD/DATA_ENGINEERING_JD (Milestone 6B/6B.1's own manual
# validation postings) -- duplicated verbatim here rather than imported
# cross-module, to keep this file self-contained and independent of the
# `tests` package's own importability (see docs/CHANGELOG_DEV.md's
# Milestone 7A entry: `from tests.X import Y` only resolves when pytest
# is invoked via `python -m pytest`, not the bare `pytest` console
# script -- a pre-existing repo quirk this file deliberately does not
# depend on).

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

Benefits:
- Unlimited PTO
- Free snacks and React JS meetups every Friday
"""

ROBOTICS_JD = """Robotics Software Engineer

The Role:
Build the software that powers our next generation of autonomous robots.

Requirements:
- Strong C++ skills required
- Proficiency in Python for tooling and scripting
- Hands-on experience with ROS2
- Prior experience with control systems or robotics

Nice to Have:
- Experience with CUDA
- Familiarity with FreeRTOS

Bachelor's degree in Computer Science, Robotics, or a related field.
Must be eligible to work in the United States.
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

DATA_ENGINEERING_JD = """Data Engineer

Responsibilities:
- Build and maintain ETL pipelines using Python
- Manage data warehousing solutions with PostgreSQL and Redis

Requirements:
- Experience with Docker
- 3+ years of experience in data engineering or a related field
- Bachelor's degree in Computer Science or equivalent experience

Nice to have:
- Experience with Snowflake or BigQuery
- Familiarity with dbt
"""


def repo(name: str, owner: str = "candidate") -> RepositoryIdentity:
    return RepositoryIdentity(owner=owner, name=name)


def ev(repo_name: str, concept: str, confidence=ConfidenceLevel.MODERATE, obs="observation") -> Evidence:
    return Evidence(
        repository=repo(repo_name),
        evidence_type=EvidenceType.DEPENDENCY,
        raw_observation=obs,
        concept_id=concept,
        confidence=confidence,
        extractor_version="test@1",
    )


def profile_from(evidence_items):
    evidence_items = tuple(evidence_items)
    repos = sorted({item.repository for item in evidence_items}, key=lambda r: (r.owner, r.name))
    return build_candidate_evidence_profile(
        "candidate", discovered=repos, analyzed=repos, evidence_items=evidence_items
    )


def by_concept(analysis: JobMatchAnalysis, concept_id: str):
    for match in analysis.requirement_matches:
        if match.requirement.concept_id == concept_id:
            return match
    return None


def by_category(analysis: JobMatchAnalysis, category: str):
    return [m for m in analysis.requirement_matches if m.requirement.category == category]


def by_alternative_containing(analysis: JobMatchAnalysis, concept_id: str):
    for match in analysis.requirement_matches:
        if match.requirement.is_alternative_group and concept_id in match.requirement.alternative_concept_ids:
            return match
    return None


# ---------------------------------------------------------------------------
# Backend Software Engineer
# ---------------------------------------------------------------------------

def test_backend_candidate_with_python_and_docker_only():
    job = parse_job_description(BACKEND_JD, title="Backend Software Engineer")
    candidate = profile_from(
        [
            ev("api-service", "language.python", confidence=ConfidenceLevel.STRONG),
            ev("api-service", "infra.docker", confidence=ConfidenceLevel.STRONG),
        ]
    )
    analysis = match_job(candidate, job)

    python_match = by_concept(analysis, "language.python")
    assert python_match.status == MatchStatus.SUPPORTED
    assert {e.repository.name for e in python_match.supporting_evidence} == {"api-service"}

    docker_match = by_concept(analysis, "infra.docker")
    assert docker_match.status == MatchStatus.SUPPORTED

    # PostgreSQL required, not observed -- never rendered as "lacks skill",
    # just the structured status.
    postgres_match = by_concept(analysis, "database.postgresql")
    assert postgres_match.status == MatchStatus.NOT_OBSERVED
    assert postgres_match.supporting_evidence == ()

    # AWS preferred, not observed -- necessity never upgrades/downgrades status.
    aws_match = by_concept(analysis, "cloud.aws")
    assert aws_match.status == MatchStatus.NOT_OBSERVED

    # The "3+ years experience" claim and the soft-skill communication
    # claim are non-observable -- never technical gaps.
    experience_matches = by_category(analysis, "experience")
    assert len(experience_matches) == 1
    assert experience_matches[0].status == MatchStatus.NOT_ASSESSABLE
    assert experience_matches[0].requirement.github_observability == GithubObservability.NOT_OBSERVABLE

    soft_skill_matches = by_category(analysis, "soft_skill")
    assert len(soft_skill_matches) == 1
    assert soft_skill_matches[0].status == MatchStatus.NOT_ASSESSABLE

    assert not hasattr(analysis, "score")
    assert not hasattr(analysis, "fit_score")


# ---------------------------------------------------------------------------
# Robotics Software Engineer
# ---------------------------------------------------------------------------

def test_robotics_candidate_with_cpp_and_ros2_only():
    job = parse_job_description(ROBOTICS_JD, title="Robotics Software Engineer")
    candidate = profile_from(
        [
            ev("nav-stack", "language.cpp", confidence=ConfidenceLevel.STRONG),
            ev("nav-stack", "robotics.ros2", confidence=ConfidenceLevel.STRONG),
        ]
    )
    analysis = match_job(candidate, job)

    assert by_concept(analysis, "language.cpp").status == MatchStatus.SUPPORTED
    assert by_concept(analysis, "robotics.ros2").status == MatchStatus.SUPPORTED

    # Python required in this posting too, but not in candidate evidence.
    python_match = by_concept(analysis, "language.python")
    assert python_match.status == MatchStatus.NOT_OBSERVED

    # Legal (work authorization) and education claims are NOT_ASSESSABLE,
    # never a "failed requirement."
    legal_matches = by_category(analysis, "legal")
    assert len(legal_matches) == 1
    assert legal_matches[0].status == MatchStatus.NOT_ASSESSABLE


# ---------------------------------------------------------------------------
# ML Engineer -- the OR-group case (Docker or Kubernetes)
# ---------------------------------------------------------------------------

def test_ml_candidate_supports_docker_side_of_or_group_not_kubernetes():
    job = parse_job_description(ML_JD, title="Machine Learning Engineer")
    candidate = profile_from(
        [
            ev("training-repo", "language.python", confidence=ConfidenceLevel.STRONG),
            ev("training-repo", "ml.framework.pytorch", confidence=ConfidenceLevel.STRONG),
            ev("training-repo", "infra.docker", confidence=ConfidenceLevel.STRONG),
        ]
    )
    analysis = match_job(candidate, job)

    assert by_concept(analysis, "language.python").status == MatchStatus.SUPPORTED
    assert by_concept(analysis, "ml.framework.pytorch").status == MatchStatus.SUPPORTED

    # "Docker or Kubernetes" -- candidate only has Docker evidence, no
    # Kubernetes evidence at all. Must be SUPPORTED via Docker ALONE
    # (never require both -- the exact false-AND bug class this
    # milestone guards against), and matched_concept_ids must name only
    # the alternative that actually matched.
    docker_or_kubernetes = by_alternative_containing(analysis, "infra.docker")
    assert docker_or_kubernetes.status == MatchStatus.SUPPORTED
    assert docker_or_kubernetes.matched_concept_ids == ("infra.docker",)
    assert "unresolved:kubernetes" not in docker_or_kubernetes.matched_concept_ids

    # "AWS or Azure" (preferred) -- candidate has neither -> NOT_OBSERVED,
    # never NOT_ASSESSABLE (it IS a real technical alternative group).
    aws_or_azure = by_alternative_containing(analysis, "cloud.aws")
    assert aws_or_azure.status == MatchStatus.NOT_OBSERVED

    # "5+ years professional software engineering experience" -> non-observable.
    experience_matches = by_category(analysis, "experience")
    assert experience_matches[0].status == MatchStatus.NOT_ASSESSABLE

    # "mentoring junior engineers" -> leadership, PARTIALLY_OBSERVABLE,
    # no concept mapping -> NOT_ASSESSABLE (not silently promoted to SUPPORTED).
    leadership_matches = by_category(analysis, "leadership")
    assert len(leadership_matches) == 1
    assert leadership_matches[0].requirement.github_observability == GithubObservability.PARTIALLY_OBSERVABLE
    assert leadership_matches[0].status == MatchStatus.NOT_ASSESSABLE


def test_ml_candidate_supports_both_sides_of_or_group_retains_both():
    job = parse_job_description(ML_JD, title="Machine Learning Engineer")
    candidate = profile_from(
        [
            ev("training-repo", "language.python"),
            ev("training-repo", "ml.framework.pytorch"),
            ev("infra-repo", "infra.docker"),
            ev("infra-repo", "infra.kubernetes"),
        ]
    )
    analysis = match_job(candidate, job)
    docker_or_kubernetes = by_alternative_containing(analysis, "infra.docker")
    assert docker_or_kubernetes.status == MatchStatus.SUPPORTED
    assert docker_or_kubernetes.matched_concept_ids == ("infra.docker", "infra.kubernetes")
    assert {e.repository.name for e in docker_or_kubernetes.supporting_evidence} == {"infra-repo"}


# ---------------------------------------------------------------------------
# Data Engineer
# ---------------------------------------------------------------------------

def test_data_engineer_candidate_with_python_and_postgres_only():
    job = parse_job_description(DATA_ENGINEERING_JD, title="Data Engineer")
    candidate = profile_from(
        [
            ev("etl-pipeline", "language.python", confidence=ConfidenceLevel.STRONG),
            ev("etl-pipeline", "database.postgresql", confidence=ConfidenceLevel.STRONG),
        ]
    )
    analysis = match_job(candidate, job)

    assert by_concept(analysis, "language.python").status == MatchStatus.SUPPORTED
    assert by_concept(analysis, "database.postgresql").status == MatchStatus.SUPPORTED

    # Redis and Docker required, no candidate evidence -> NOT_OBSERVED.
    assert by_concept(analysis, "database.redis").status == MatchStatus.NOT_OBSERVED
    assert by_concept(analysis, "infra.docker").status == MatchStatus.NOT_OBSERVED

    # Education claim ("Bachelor's degree ... or equivalent experience")
    # is non-technical -> NOT_ASSESSABLE, never a gap.
    education_matches = by_category(analysis, "education")
    assert len(education_matches) == 1
    assert education_matches[0].status == MatchStatus.NOT_ASSESSABLE


def test_no_requirement_match_ever_reports_supported_without_evidence_across_all_four_postings():
    # Cross-cutting structural guarantee across all four fixtures at
    # once: SUPPORTED always carries real, attributable Evidence.
    postings = [
        (BACKEND_JD, "Backend Software Engineer"),
        (ROBOTICS_JD, "Robotics Software Engineer"),
        (ML_JD, "Machine Learning Engineer"),
        (DATA_ENGINEERING_JD, "Data Engineer"),
    ]
    empty_candidate = profile_from([])
    for raw_text, title in postings:
        job = parse_job_description(raw_text, title=title)
        analysis = match_job(empty_candidate, job)
        for match in analysis.requirement_matches:
            if match.status == MatchStatus.SUPPORTED:
                assert match.supporting_evidence  # pragma: no cover -- would only fire on a real bug
            else:
                assert match.supporting_evidence == ()
        # No candidate evidence at all -> every technical requirement is
        # NOT_OBSERVED (never SUPPORTED), and no score-like attribute exists.
        assert not any(m.status == MatchStatus.SUPPORTED for m in analysis.requirement_matches)
        assert not hasattr(analysis, "score")
