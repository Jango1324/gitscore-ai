"""Milestone 6B -- end-to-end gitscore.jobs.parse_job_description() tests:
input validation, provenance, compound requirements, alternatives,
non-technical requirements, unknown-tech policy, and Part 19's manual
real-world validation examples (backend / robotics / ML / data
engineering).
"""
import pytest

from gitscore.jobs import GithubObservability, Importance, JobRequirementProfile, Necessity, parse_job_description
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION


# ---------------------------------------------------------------------------
# INPUT
# ---------------------------------------------------------------------------

def test_empty_description_is_rejected():
    with pytest.raises(ValueError):
        parse_job_description("")


def test_whitespace_only_description_is_rejected():
    with pytest.raises(ValueError):
        parse_job_description("   \n  ")


def test_title_is_preserved():
    profile = parse_job_description("Requirements:\n- Python\n", title="Backend Engineer")
    assert profile.title == "Backend Engineer"


def test_company_is_preserved():
    profile = parse_job_description("Requirements:\n- Python\n", company="Acme Corp")
    assert profile.company == "Acme Corp"


def test_title_and_company_default_to_none():
    profile = parse_job_description("Requirements:\n- Python\n")
    assert profile.title is None
    assert profile.company is None


def test_original_description_is_preserved_verbatim():
    description = "Requirements:\n- Python\n- PostgreSQL\n\nBenefits:\n- Free coffee\n"
    profile = parse_job_description(description)
    assert profile.raw_text == description


def test_returns_the_existing_job_requirement_profile_type():
    profile = parse_job_description("Requirements:\n- Python\n")
    assert isinstance(profile, JobRequirementProfile)


def test_parser_version_is_stamped():
    profile = parse_job_description("Requirements:\n- Python\n")
    assert profile.parser_version == JOB_DESCRIPTION_PARSER_VERSION


# ---------------------------------------------------------------------------
# PROVENANCE (Part 11)
# ---------------------------------------------------------------------------

def test_every_requirement_span_is_an_exact_substring_of_the_description():
    description = (
        "Requirements:\n"
        "- 3+ years of experience building Python backend services\n"
        "- Experience with PostgreSQL\n"
    )
    profile = parse_job_description(description)
    assert profile.requirement_count > 0
    for requirement in profile.requirements:
        span = requirement.source_span
        assert span is not None
        assert description[span.start:span.end] == requirement.original_text


def test_multiple_requirements_from_one_claim_share_the_same_source_span():
    description = "Requirements:\n- 3+ years of experience building Python backend services\n"
    profile = parse_job_description(description)
    spans = {r.source_span for r in profile.requirements}
    assert len(spans) == 1
    assert len(profile.requirements) == 2  # technical Python + non-technical experience


# ---------------------------------------------------------------------------
# COMPOUND requirements (Part 4)
# ---------------------------------------------------------------------------

def test_python_and_postgresql_produces_two_requirements():
    profile = parse_job_description("Requirements:\n- Experience with Python and PostgreSQL\n")
    concept_ids = {r.concept_id for r in profile.requirements}
    assert concept_ids == {"language.python", "database.postgresql"}


def test_python_postgresql_and_docker_produces_three_requirements():
    profile = parse_job_description("Requirements:\n- Experience with Python, PostgreSQL, and Docker\n")
    concept_ids = {r.concept_id for r in profile.requirements}
    assert concept_ids == {"language.python", "database.postgresql", "infra.docker"}


def test_compound_experience_sentence_produces_technical_and_experience_requirements():
    description = "Requirements:\n- 3+ years of experience building Python backend services\n"
    profile = parse_job_description(description)
    technical = [r for r in profile.requirements if r.is_technical]
    non_technical = [r for r in profile.requirements if not r.is_technical]
    assert len(technical) == 1
    assert technical[0].concept_id == "language.python"
    assert technical[0].github_observability == GithubObservability.STRONGLY_OBSERVABLE
    assert len(non_technical) == 1
    assert non_technical[0].category == "experience"
    assert non_technical[0].github_observability == GithubObservability.NOT_OBSERVABLE


# ---------------------------------------------------------------------------
# ALTERNATIVES / OR (Part 14) -- must NEVER become AND
# ---------------------------------------------------------------------------

def test_python_or_go_does_not_produce_two_independent_required_rows():
    # Milestone 6B.1: structured alternative group, not two independent
    # single-concept REQUIRED rows -- the future matcher evaluates
    # supported(Python) OR supported(Go), never both unconditionally.
    profile = parse_job_description("Requirements:\n- Python or Go experience\n")
    single_concept_rows = [r for r in profile.requirements if r.concept_id is not None]
    assert single_concept_rows == []
    assert profile.requirement_count == 1
    group = profile.requirements[0]
    assert group.is_alternative_group
    assert group.concept_id is None
    assert group.alternative_concept_ids == ("language.go", "language.python")
    assert group.necessity == Necessity.REQUIRED


def test_aws_or_azure_is_one_structured_alternative_group():
    profile = parse_job_description("Requirements:\n- Experience with AWS or Azure\n")
    single_concept_rows = [r for r in profile.requirements if r.concept_id is not None]
    assert single_concept_rows == []
    assert profile.requirement_count == 1
    group = profile.requirements[0]
    assert group.is_alternative_group
    assert group.alternative_concept_ids == ("cloud.aws", "unresolved:azure")


def test_go_or_python_is_the_same_alternative_set_as_python_or_go():
    a = parse_job_description("Requirements:\n- Python or Go\n").requirements[0]
    b = parse_job_description("Requirements:\n- Go or Python\n").requirements[0]
    assert a.alternative_concept_ids == b.alternative_concept_ids == ("language.go", "language.python")


def test_postgresql_mysql_or_mongodb_is_one_three_way_alternative_group():
    profile = parse_job_description("Requirements:\n- Experience with PostgreSQL, MySQL, or MongoDB\n")
    assert profile.requirement_count == 1
    group = profile.requirements[0]
    assert group.is_alternative_group
    assert group.alternative_concept_ids == ("database.postgresql", "unresolved:mongodb", "unresolved:mysql")


def test_resolved_alternative_group_has_high_parser_confidence():
    from gitscore.jobs.types import ParserConfidence

    profile = parse_job_description("Requirements:\n- Python or Go\n")
    assert profile.requirements[0].parser_confidence == ParserConfidence.HIGH


def test_unsafe_alternative_falls_back_to_the_conservative_placeholder_with_low_confidence():
    from gitscore.jobs.types import ParserConfidence

    # "a genuinely amazing attitude" fails the conservative shape check --
    # the group can't be safely built, so this falls back to the OLD
    # non-technical placeholder instead of dropping Python's alternative
    # or inventing a reckless unresolved id for "attitude".
    profile = parse_job_description("Requirements:\n- Python or a genuinely amazing attitude\n")
    assert profile.requirement_count == 1
    r = profile.requirements[0]
    assert not r.is_alternative_group
    assert r.concept_id is None
    assert r.category == "alternative_requirement"
    assert r.parser_confidence == ParserConfidence.LOW


def test_alternative_group_preserves_original_text_verbatim():
    profile = parse_job_description("Requirements:\n- Python or Go experience\n")
    assert profile.requirements[0].original_text == "Python or Go experience"


def test_required_python_or_go_has_one_required_group():
    profile = parse_job_description("Requirements:\n- Python or Go required\n")
    assert profile.requirement_count == 1
    assert profile.requirements[0].necessity == Necessity.REQUIRED
    assert profile.requirements[0].alternative_concept_ids == ("language.go", "language.python")


def test_python_or_go_preferred_has_one_preferred_group():
    profile = parse_job_description("Preferred Qualifications:\n- Python or Go\n")
    assert profile.requirement_count == 1
    assert profile.requirements[0].necessity == Necessity.PREFERRED


def test_bachelors_degree_or_related_field_is_not_a_fake_technical_alternative_group():
    profile = parse_job_description(
        "Requirements:\n- Bachelor's degree in Computer Science or related field\n"
    )
    assert profile.requirement_count == 1
    r = profile.requirements[0]
    assert not r.is_alternative_group
    assert r.concept_id is None
    assert r.category == "education"


def test_experience_or_equivalent_education_is_not_a_fake_technical_alternative_group():
    profile = parse_job_description("Requirements:\n- 3+ years experience or equivalent education\n")
    for r in profile.requirements:
        assert not r.is_alternative_group
        assert r.category != "alternative_requirement"


def test_plain_and_list_is_not_treated_as_an_alternative():
    profile = parse_job_description("Requirements:\n- React and TypeScript\n")
    concept_ids = {r.concept_id for r in profile.requirements}
    assert concept_ids == {"framework.react", "language.typescript"}


# ---------------------------------------------------------------------------
# NON-TECHNICAL requirements (Part 10)
# ---------------------------------------------------------------------------

def test_professional_experience_is_preserved_as_non_technical():
    profile = parse_job_description("Requirements:\n- 5+ years of professional experience\n")
    assert len(profile.requirements) == 1
    r = profile.requirements[0]
    assert r.concept_id is None
    assert r.category == "experience"
    assert r.github_observability == GithubObservability.NOT_OBSERVABLE


def test_degree_is_preserved_as_non_technical():
    profile = parse_job_description("Requirements:\n- Bachelor's degree in Computer Science\n")
    r = profile.requirements[0]
    assert r.concept_id is None
    assert r.category == "education"
    assert r.github_observability == GithubObservability.NOT_OBSERVABLE


def test_communication_is_preserved_as_non_technical():
    profile = parse_job_description("Requirements:\n- Excellent written and verbal communication\n")
    r = profile.requirements[0]
    assert r.concept_id is None
    assert r.category == "soft_skill"
    assert r.github_observability == GithubObservability.NOT_OBSERVABLE


def test_work_authorization_is_preserved_as_non_technical():
    profile = parse_job_description("Requirements:\n- Must be eligible to work in Canada\n")
    r = profile.requirements[0]
    assert r.concept_id is None
    assert r.category == "legal"
    assert r.github_observability == GithubObservability.NOT_OBSERVABLE


def test_mentoring_is_preserved_as_non_technical():
    profile = parse_job_description("Requirements:\n- Experience mentoring junior engineers\n")
    r = profile.requirements[0]
    assert r.concept_id is None
    assert r.category == "leadership"
    assert r.github_observability == GithubObservability.PARTIALLY_OBSERVABLE


def test_no_fake_technical_concept_ids_are_manufactured_for_non_technical_requirements():
    profile = parse_job_description(
        "Requirements:\n- Bachelor's degree\n- Excellent communication\n- 3+ years of experience\n"
    )
    for r in profile.requirements:
        if r.concept_id is not None:
            assert not r.concept_id.startswith("skill.")
            assert not r.concept_id.startswith("education.")
            assert not r.concept_id.startswith("experience.")


# ---------------------------------------------------------------------------
# UNKNOWN TECH policy (Part 5)
# ---------------------------------------------------------------------------

def test_clearly_technical_unknown_term_is_retained_conservatively():
    # Milestone 8D.1: uses a deliberately synthetic, guaranteed-unregistered
    # term (not a real technology like Kubernetes, which is now a
    # registered concept) so this test keeps exercising the "unresolved
    # term co-listed with known concepts is preserved" behavior regardless
    # of future registry additions.
    profile = parse_job_description(
        "Requirements:\n- Experience with Python, SomeUnknownOrchestrator, and Docker\n"
    )
    concept_ids = {r.concept_id for r in profile.requirements}
    assert "language.python" in concept_ids
    assert "infra.docker" in concept_ids
    assert any(cid is not None and cid.startswith("unresolved:someunknownorchestrator") for cid in concept_ids)


def test_ordinary_unknown_prose_is_not_promoted_to_an_unresolved_concept():
    profile = parse_job_description("Requirements:\n- Strong communication skills and a positive attitude\n")
    for r in profile.requirements:
        assert r.concept_id is None or not r.concept_id.startswith("unresolved:")


def test_bare_verb_phrase_does_not_produce_a_false_positive_unresolved_concept():
    # Regression guard for a real false positive found during Milestone
    # 6B's manual validation: "Build and maintain ETL pipelines using
    # Python" must not promote "Build" to unresolved:build.
    profile = parse_job_description("Responsibilities:\n- Build and maintain ETL pipelines using Python\n")
    concept_ids = {r.concept_id for r in profile.requirements}
    assert "unresolved:build" not in concept_ids
    assert "language.python" in concept_ids


def test_purpose_clause_does_not_produce_a_false_positive_unresolved_concept():
    # Regression guard: "Proficiency in Python for tooling and
    # scripting" must not promote "scripting" to unresolved:scripting.
    profile = parse_job_description("Requirements:\n- Proficiency in Python for tooling and scripting\n")
    concept_ids = {r.concept_id for r in profile.requirements}
    assert "unresolved:scripting" not in concept_ids
    assert "language.python" in concept_ids


# ---------------------------------------------------------------------------
# ALIAS SAFETY regression (Part 6) -- no regression to README extraction policy
# ---------------------------------------------------------------------------

def test_next_steps_phrase_does_not_imply_nextjs_end_to_end():
    profile = parse_job_description(
        "Requirements:\n- Python\n\nWe will discuss next steps after the interview.\n"
    )
    concept_ids = {r.concept_id for r in profile.requirements}
    assert "framework.nextjs" not in concept_ids


def test_ordinary_go_phrase_does_not_imply_language_go_end_to_end():
    profile = parse_job_description(
        "Requirements:\n- Python\n\nWe go above and beyond for our customers.\n"
    )
    concept_ids = {r.concept_id for r in profile.requirements}
    assert "language.go" not in concept_ids


def test_readme_extraction_itself_is_unaffected_by_the_jobs_package():
    from gitscore.evidence.extraction.readme import evidence_from_readme

    evidence = evidence_from_readme("octocat", "repo", "Built with PostgreSQL.", "README.md")
    assert [e.concept_id for e in evidence] == ["database.postgresql"]


# ---------------------------------------------------------------------------
# Part 19 -- manual real-world validation (4 distinct technical roles)
# ---------------------------------------------------------------------------

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


def test_manual_validation_backend():
    profile = parse_job_description(BACKEND_JD, title="Backend Software Engineer")
    concept_ids = {r.concept_id for r in profile.requirements}
    assert {"language.python", "database.postgresql", "infra.docker", "cloud.aws", "framework.nextjs"} <= concept_ids
    # Benefits/marketing prose never leaks into requirements.
    assert not any("PTO" in r.original_text or "snacks" in r.original_text for r in profile.requirements)
    # "React JS meetups" in the Benefits section must never produce framework.react evidence.
    assert "framework.react" not in concept_ids
    experience_rows = [r for r in profile.requirements if r.category == "experience"]
    assert len(experience_rows) == 1
    assert experience_rows[0].github_observability == GithubObservability.NOT_OBSERVABLE


def test_manual_validation_robotics():
    profile = parse_job_description(ROBOTICS_JD, title="Robotics Software Engineer")
    concept_ids = {r.concept_id for r in profile.requirements}
    assert {"language.cpp", "language.python", "robotics.ros2", "platform.cuda", "embedded.rtos.freertos"} <= concept_ids
    # "control systems or robotics" -- neither side is a registered
    # concept, so this is correctly judged NOT a technical alternative
    # group at all (Milestone 6B.1: no confirmed concept anywhere in the
    # OR-list). It must never assert a fake technical concept, and (a
    # known, documented limitation) produces no row at all since no
    # other detector matches it either.
    assert not any("control systems or robotics" in r.original_text for r in profile.requirements)
    legal_rows = [r for r in profile.requirements if r.category == "legal"]
    assert len(legal_rows) == 1
    assert legal_rows[0].github_observability == GithubObservability.NOT_OBSERVABLE


def test_manual_validation_ml():
    profile = parse_job_description(ML_JD, title="Machine Learning Engineer")
    concept_ids = {r.concept_id for r in profile.requirements}
    assert {"language.python", "ml.framework.pytorch"} <= concept_ids
    # "Docker or Kubernetes" must never produce two independent REQUIRED rows.
    assert "infra.docker" not in concept_ids or all(
        r.necessity != Necessity.REQUIRED for r in profile.requirements if r.concept_id == "infra.docker"
    )
    technical_docker_or_kubernetes = [r for r in profile.requirements if r.concept_id in ("infra.docker",)]
    assert technical_docker_or_kubernetes == []  # never a lone, unconditional Docker requirement
    # Milestone 6B.1: structured instead -- a real alternative group.
    docker_group = next(r for r in profile.requirements if r.is_alternative_group and "infra.docker" in r.alternative_concept_ids)
    assert docker_group.alternative_concept_ids == ("infra.docker", "infra.kubernetes")
    leadership_rows = [r for r in profile.requirements if r.category == "leadership"]
    assert len(leadership_rows) == 1


def test_manual_validation_data_engineering():
    profile = parse_job_description(DATA_ENGINEERING_JD, title="Data Engineer")
    concept_ids = {r.concept_id for r in profile.requirements}
    assert {"language.python", "database.postgresql", "database.redis", "infra.docker"} <= concept_ids
    # Known false positive already fixed: "Build" must never appear as unresolved:build.
    assert "unresolved:build" not in concept_ids
    # Known accepted false negative (documented): a standalone "Familiarity with dbt"
    # bullet with no co-occurring known concept in the same claim produces nothing.
    assert not any(cid is not None and "dbt" in cid for cid in concept_ids)


# ---------------------------------------------------------------------------
# Regression -- Milestone 6A/6A.1 objects unchanged
# ---------------------------------------------------------------------------

def test_job_requirement_profile_still_rejects_arbitrary_concept_ids():
    from gitscore.jobs import JobRequirement

    with pytest.raises(ValueError):
        JobRequirement(
            original_text="Experience with X",
            necessity=Necessity.REQUIRED,
            importance=Importance.MEDIUM,
            github_observability=GithubObservability.STRONGLY_OBSERVABLE,
            concept_id="whatever.random.string",
        )
