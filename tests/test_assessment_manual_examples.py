"""Milestone 7B Part 18 -- manual end-to-end validation of
`assess_job()` against the four real, hand-written job postings already
used for Milestone 6B/6B.1's parser validation and Milestone 7A's
matcher validation (`tests/test_job_parser.py` /
`tests/test_matching_manual_examples.py` -- BACKEND_JD, ROBOTICS_JD,
ML_JD, DATA_ENGINEERING_JD), each run through the REAL
`parse_job_description()` and the REAL `match_job()`, then assessed with
the REAL `assess_job()`.

Full pipeline exercised per posting:

    raw job description text
        -> parse_job_description()      (Milestone 6B)
        -> JobRequirementProfile
        +  hand-built CandidateEvidenceProfile
        -> match_job()                  (Milestone 7A)
        -> JobMatchAnalysis
        -> assess_job()                 (Milestone 7B)
        -> JobAssessment

No real GitHub API call anywhere -- every `Evidence` item is
hand-constructed. This file asserts there is NO rematching inside
`assess_job()`, NO score weighting, NO coverage percentage, NO
hire/reject verdict, and NO generated explanation prose anywhere in the
resulting `JobAssessment`.
"""
from __future__ import annotations

import dataclasses

from gitscore.assessment import JobAssessment, SubscoreFacts, assess_job
from gitscore.evidence import ConfidenceLevel, Evidence, EvidenceType, RepositoryIdentity, build_candidate_evidence_profile
from gitscore.jobs import parse_job_description
from gitscore.matching import MatchStatus, match_job

# Identical fixture text to tests/test_matching_manual_examples.py (itself
# identical to tests/test_job_parser.py's own BACKEND_JD/ROBOTICS_JD/ML_JD/
# DATA_ENGINEERING_JD) -- duplicated verbatim here rather than imported
# cross-module, for the same self-containment reason that file documents.

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


def ev(repo_name: str, concept: str, confidence=ConfidenceLevel.MODERATE) -> Evidence:
    return Evidence(
        repository=repo(repo_name),
        evidence_type=EvidenceType.DEPENDENCY,
        raw_observation="observation",
        concept_id=concept,
        confidence=confidence,
        extractor_version="test@1",
    )


def profile_from(evidence_items, discovered_extra=()):
    evidence_items = tuple(evidence_items)
    repos = sorted({item.repository for item in evidence_items}, key=lambda r: (r.owner, r.name))
    discovered = sorted(set(repos) | set(discovered_extra), key=lambda r: (r.owner, r.name))
    return build_candidate_evidence_profile(
        "candidate", discovered=discovered, analyzed=repos, evidence_items=evidence_items
    )


def assess(raw_text, title, evidence_items, discovered_extra=()):
    job = parse_job_description(raw_text, title=title)
    candidate = profile_from(evidence_items, discovered_extra=discovered_extra)
    analysis = match_job(candidate, job)
    return analysis, assess_job(analysis)


def _assert_no_rematching_no_prose(analysis, assessment: JobAssessment):
    assert assessment.match_analysis is analysis
    assert assessment.match_analysis.requirement_matches is analysis.requirement_matches
    field_names = {f.name for f in dataclasses.fields(assessment)}
    assert field_names == {"match_analysis", "scoring_version"}
    for attr in ("explanation", "summary", "coverage_note", "coverage_percentage", "hire_recommendation", "fit_verdict"):
        assert not hasattr(assessment, attr)


# ---------------------------------------------------------------------------
# Backend Software Engineer
# ---------------------------------------------------------------------------

def test_backend_assessment_python_and_docker_only():
    analysis, assessment = assess(
        BACKEND_JD,
        "Backend Software Engineer",
        [
            ev("api-service", "language.python", confidence=ConfidenceLevel.STRONG),
            ev("api-service", "infra.docker", confidence=ConfidenceLevel.STRONG),
        ],
    )
    _assert_no_rematching_no_prose(analysis, assessment)

    # Real parser output (6A Part 1 splitting): "3+ years of experience
    # building Python backend services" becomes TWO requirements -- a
    # technical language.python one (STRONGLY_OBSERVABLE) and a
    # non-technical "experience" one (NOT_OBSERVABLE) -- plus required
    # PostgreSQL/Docker and preferred AWS/Next.js, all technical.
    # Assessable set: python, postgresql, docker, aws, nextjs = 5.
    # Supported (python, docker) = 2 -> 200/5 = 40.
    assert assessment.assessable_count == 5
    assert assessment.alignment_score == 40
    assert assessment.required == SubscoreFacts(supported=2, assessable=3)  # python+docker supported, postgresql not
    assert assessment.preferred == SubscoreFacts(supported=0, assessable=2)  # aws, next.js not observed

    supported_texts = {m.requirement.original_text for m in assessment.supported_matches()}
    assert any("Docker" in t for t in supported_texts)

    not_assessable_texts = {m.requirement.original_text for m in assessment.not_assessable_matches()}
    assert any("experience" in t.lower() for t in not_assessable_texts)
    assert any("communication" in t.lower() for t in not_assessable_texts)


# ---------------------------------------------------------------------------
# Robotics Software Engineer
# ---------------------------------------------------------------------------

def test_robotics_assessment_cpp_and_ros2_only():
    analysis, assessment = assess(
        ROBOTICS_JD,
        "Robotics Software Engineer",
        [
            ev("nav-stack", "language.cpp", confidence=ConfidenceLevel.STRONG),
            ev("nav-stack", "robotics.ros2", confidence=ConfidenceLevel.STRONG),
        ],
    )
    _assert_no_rematching_no_prose(analysis, assessment)

    # C++, Python, ROS2 all required and technical; CUDA/FreeRTOS preferred.
    assert assessment.required is not None
    assert assessment.required.supported == 2  # C++, ROS2 (Python not observed)
    assert assessment.required.assessable == 3
    assert assessment.preferred == SubscoreFacts(supported=0, assessable=2)

    legal_education = [m for m in assessment.not_assessable_matches()]
    assert any(m.requirement.category in ("legal", "education") for m in legal_education)


# ---------------------------------------------------------------------------
# ML Engineer -- OR group (Docker or Kubernetes)
# ---------------------------------------------------------------------------

def test_ml_assessment_or_group_counts_once():
    analysis, assessment = assess(
        ML_JD,
        "Machine Learning Engineer",
        [
            ev("training-repo", "language.python", confidence=ConfidenceLevel.STRONG),
            ev("training-repo", "ml.framework.pytorch", confidence=ConfidenceLevel.STRONG),
            ev("training-repo", "infra.docker", confidence=ConfidenceLevel.STRONG),
        ],
    )
    _assert_no_rematching_no_prose(analysis, assessment)

    or_group_match = next(m for m in analysis.requirement_matches if m.requirement.is_alternative_group)
    assert or_group_match.status == MatchStatus.SUPPORTED
    # The OR group is exactly ONE RequirementMatch, counted once in the
    # assessable set -- not once per alternative.
    assert sum(1 for m in assessment.supported_matches() if m.requirement.is_alternative_group) == 1

    # "mentoring junior engineers" (leadership, PARTIALLY_OBSERVABLE, no
    # concept mapping) is NOT_ASSESSABLE -- never counted as a gap.
    leadership = [m for m in assessment.not_assessable_matches() if m.requirement.category == "leadership"]
    assert len(leadership) == 1

    # "5+ years professional experience" NOT_ASSESSABLE too.
    experience = [m for m in assessment.not_assessable_matches() if m.requirement.category == "experience"]
    assert len(experience) == 1


# ---------------------------------------------------------------------------
# Data Engineer
# ---------------------------------------------------------------------------

def test_data_engineer_assessment_python_and_postgres_only():
    analysis, assessment = assess(
        DATA_ENGINEERING_JD,
        "Data Engineer",
        [
            ev("etl-pipeline", "language.python", confidence=ConfidenceLevel.STRONG),
            ev("etl-pipeline", "database.postgresql", confidence=ConfidenceLevel.STRONG),
        ],
    )
    _assert_no_rematching_no_prose(analysis, assessment)

    assert assessment.alignment_score is not None
    assert 0 <= assessment.alignment_score <= 100

    not_observed_concepts = {
        m.requirement.concept_id for m in assessment.not_observed_matches() if m.requirement.concept_id
    }
    assert "database.redis" in not_observed_concepts
    assert "infra.docker" in not_observed_concepts

    education = [m for m in assessment.not_assessable_matches() if m.requirement.category == "education"]
    assert len(education) == 1


# ---------------------------------------------------------------------------
# Cross-cutting: repository coverage facts pass through unmodified, no
# coverage percentage invented anywhere.
# ---------------------------------------------------------------------------

def test_coverage_facts_pass_through_unmodified_no_percentage_invented():
    discovered_extra = [repo(f"unexamined-{i}") for i in range(5)]
    analysis, assessment = assess(
        BACKEND_JD,
        "Backend Software Engineer",
        [ev("api-service", "infra.docker")],
        discovered_extra=discovered_extra,
    )
    coverage = assessment.match_analysis.coverage
    assert coverage is analysis.coverage
    assert coverage.discovered_count == 6
    assert coverage.analyzed_count == 1
    assert coverage.is_complete is False
    # No coverage percentage field exists anywhere on JobAssessment.
    assert not hasattr(assessment, "coverage_percentage")
    assert not hasattr(assessment, "evidence_coverage")


def test_low_parser_confidence_count_present_across_all_four_postings():
    for raw_text, title in [
        (BACKEND_JD, "Backend Software Engineer"),
        (ROBOTICS_JD, "Robotics Software Engineer"),
        (ML_JD, "Machine Learning Engineer"),
        (DATA_ENGINEERING_JD, "Data Engineer"),
    ]:
        _, assessment = assess(raw_text, title, [])
        assert isinstance(assessment.low_parser_confidence_count, int)
        assert assessment.low_parser_confidence_count >= 0
        assert assessment.low_parser_confidence_count <= assessment.assessable_count
