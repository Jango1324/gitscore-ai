"""Milestone 6A Part 12 -- manual, hand-constructed examples proving that
ONE generic domain model (JobRequirement / JobRequirementProfile)
represents radically different technical jobs without any role-specific
schema, enum-of-roles, or per-role field.

These are DOMAIN MODEL examples only: no parsing of these job
descriptions is automated (every JobRequirement below is hand-built,
exactly like every other Milestone 6A test), no candidate is scored
against them, and no matcher exists yet. The only thing under test is
"does the SAME JobRequirement/JobRequirementProfile shape hold every one
of these jobs' requirements correctly."
"""
from gitscore.concepts.registry import resolve_concept
from gitscore.jobs import (
    GithubObservability,
    Importance,
    JobRequirement,
    JobRequirementProfile,
    Necessity,
    ParserConfidence,
)

NOT_OBS = GithubObservability.NOT_OBSERVABLE
WEAK_OBS = GithubObservability.PARTIALLY_OBSERVABLE
STRONG_OBS = GithubObservability.STRONGLY_OBSERVABLE
REQUIRED = Necessity.REQUIRED
PREFERRED = Necessity.PREFERRED


def _concept(term: str) -> str:
    return resolve_concept(term).concept_id


# ---------------------------------------------------------------------------
# A) Backend Software Engineer
# ---------------------------------------------------------------------------

def _backend_profile() -> JobRequirementProfile:
    requirements = (
        JobRequirement(
            original_text="Strong proficiency in Python",
            necessity=REQUIRED,
            importance=Importance.HIGH,
            github_observability=STRONG_OBS,
            concept_id=_concept("Python"),
            category="language",
        ),
        JobRequirement(
            original_text="Experience with PostgreSQL",
            necessity=REQUIRED,
            importance=Importance.MEDIUM,
            github_observability=STRONG_OBS,
            concept_id=_concept("PostgreSQL"),
            category="database",
        ),
        JobRequirement(
            original_text="Experience designing RESTful APIs",
            necessity=REQUIRED,
            importance=Importance.MEDIUM,
            github_observability=WEAK_OBS,
            concept_id=_concept("REST APIs"),
            category="practice",
            parser_confidence=ParserConfidence.MEDIUM,
        ),
        JobRequirement(
            original_text="Familiarity with Docker is a plus",
            necessity=PREFERRED,
            importance=Importance.MEDIUM,
            github_observability=STRONG_OBS,
            concept_id=_concept("Docker"),
            category="infrastructure",
        ),
        JobRequirement(
            original_text="AWS experience preferred",
            necessity=PREFERRED,
            importance=Importance.LOW,
            github_observability=WEAK_OBS,
            concept_id=_concept("AWS"),
            category="cloud",
        ),
        JobRequirement(
            original_text="Excellent written and verbal communication",
            necessity=REQUIRED,
            importance=Importance.MEDIUM,
            github_observability=NOT_OBS,
            concept_id=None,
            category="soft_skill",
        ),
    )
    return JobRequirementProfile(
        raw_text=(
            "Backend Software Engineer\n"
            "Strong proficiency in Python. Experience with PostgreSQL. "
            "Experience designing RESTful APIs. Familiarity with Docker is a "
            "plus. AWS experience preferred. Excellent written and verbal "
            "communication."
        ),
        requirements=requirements,
        parser_version="manual:v1",
        title="Backend Software Engineer",
    )


def test_backend_job_requirements_shape():
    profile = _backend_profile()
    assert profile.title == "Backend Software Engineer"
    assert profile.requirement_count == 6

    by_concept = {r.concept_id: r for r in profile.requirements if r.is_technical}
    assert by_concept["language.python"].necessity == REQUIRED
    assert by_concept["database.postgresql"].github_observability == STRONG_OBS
    assert by_concept["infra.docker"].necessity == PREFERRED
    assert by_concept["cloud.aws"].github_observability == WEAK_OBS

    non_technical = [r for r in profile.requirements if not r.is_technical]
    assert len(non_technical) == 1
    assert non_technical[0].github_observability == NOT_OBS
    assert non_technical[0].category == "soft_skill"


# ---------------------------------------------------------------------------
# B) Robotics Software Engineer
# ---------------------------------------------------------------------------

def _robotics_profile() -> JobRequirementProfile:
    requirements = (
        JobRequirement(
            original_text="Strong C++ skills",
            necessity=REQUIRED,
            importance=Importance.HIGH,
            github_observability=STRONG_OBS,
            concept_id=_concept("C++"),
            category="language",
        ),
        JobRequirement(
            original_text="Proficiency in Python for tooling and scripting",
            necessity=REQUIRED,
            importance=Importance.MEDIUM,
            github_observability=STRONG_OBS,
            concept_id=_concept("Python"),
            category="language",
        ),
        JobRequirement(
            original_text="Hands-on experience with ROS2",
            necessity=REQUIRED,
            importance=Importance.HIGH,
            github_observability=STRONG_OBS,
            concept_id=_concept("ROS2"),
            category="robotics",
        ),
        JobRequirement(
            original_text="Comfortable working in Linux environments",
            necessity=REQUIRED,
            importance=Importance.MEDIUM,
            github_observability=WEAK_OBS,
            # Unanticipated-at-registry-design-time term -- retained via
            # the SAME unresolved:<term> policy Evidence already uses,
            # never dropped and never silently invented as a new
            # canonical concept.
            concept_id=_concept("Linux"),
            category="platform",
        ),
        JobRequirement(
            original_text="Prior experience with control systems or robotics",
            necessity=REQUIRED,
            importance=Importance.HIGH,
            github_observability=WEAK_OBS,
            concept_id=None,
            category="domain_experience",
            parser_confidence=ParserConfidence.MEDIUM,
        ),
        JobRequirement(
            original_text="Ability to work well within a cross-functional team",
            necessity=PREFERRED,
            importance=Importance.LOW,
            github_observability=NOT_OBS,
            concept_id=None,
            category="soft_skill",
        ),
    )
    return JobRequirementProfile(
        raw_text=(
            "Robotics Software Engineer\n"
            "Strong C++ skills. Proficiency in Python for tooling and "
            "scripting. Hands-on experience with ROS2. Comfortable working "
            "in Linux environments. Prior experience with control systems "
            "or robotics. Ability to work well within a cross-functional "
            "team."
        ),
        requirements=requirements,
        parser_version="manual:v1",
        title="Robotics Software Engineer",
    )


def test_robotics_job_requirements_shape():
    profile = _robotics_profile()
    assert profile.requirement_count == 6

    by_concept = {r.concept_id: r for r in profile.requirements if r.is_technical}
    assert by_concept["language.cpp"].importance == Importance.HIGH
    assert by_concept["robotics.ros2"].concept_id == "robotics.ros2"
    linux_req = by_concept["unresolved:linux"]
    assert linux_req.is_unresolved_concept
    assert not linux_req.is_resolved_concept

    domain_experience = next(r for r in profile.requirements if r.category == "domain_experience")
    assert domain_experience.concept_id is None
    assert domain_experience.github_observability == WEAK_OBS


# ---------------------------------------------------------------------------
# C) ML Engineer
# ---------------------------------------------------------------------------

def _ml_profile() -> JobRequirementProfile:
    requirements = (
        JobRequirement(
            original_text="Expert-level Python",
            necessity=REQUIRED,
            importance=Importance.HIGH,
            github_observability=STRONG_OBS,
            concept_id=_concept("Python"),
            category="language",
        ),
        JobRequirement(
            original_text="Deep experience with PyTorch",
            necessity=REQUIRED,
            importance=Importance.HIGH,
            github_observability=STRONG_OBS,
            concept_id=_concept("PyTorch"),
            category="ml_framework",
        ),
        JobRequirement(
            original_text="Experience training and evaluating deep learning models",
            necessity=REQUIRED,
            importance=Importance.HIGH,
            github_observability=WEAK_OBS,
            concept_id=_concept("model training"),
            category="ml_practice",
            parser_confidence=ParserConfidence.MEDIUM,
        ),
        JobRequirement(
            original_text="Docker experience is a plus",
            necessity=PREFERRED,
            importance=Importance.MEDIUM,
            github_observability=STRONG_OBS,
            concept_id=_concept("Docker"),
            category="infrastructure",
        ),
        JobRequirement(
            original_text="Experience deploying models to cloud platforms",
            necessity=PREFERRED,
            importance=Importance.MEDIUM,
            github_observability=WEAK_OBS,
            concept_id=_concept("cloud platforms"),
            category="cloud",
        ),
        JobRequirement(
            original_text="5+ years of professional software engineering experience",
            necessity=REQUIRED,
            importance=Importance.MEDIUM,
            github_observability=NOT_OBS,
            concept_id=None,
            category="experience",
        ),
    )
    return JobRequirementProfile(
        raw_text=(
            "Machine Learning Engineer\n"
            "Expert-level Python. Deep experience with PyTorch. Experience "
            "training and evaluating deep learning models. Docker "
            "experience is a plus. Experience deploying models to cloud "
            "platforms. 5+ years of professional software engineering "
            "experience."
        ),
        requirements=requirements,
        parser_version="manual:v1",
        title="Machine Learning Engineer",
    )


def test_ml_job_requirements_shape():
    profile = _ml_profile()
    assert profile.requirement_count == 6

    by_concept = {r.concept_id: r for r in profile.requirements if r.is_technical}
    assert by_concept["ml.framework.pytorch"].necessity == REQUIRED
    assert by_concept["unresolved:model_training"].is_unresolved_concept

    experience_req = next(r for r in profile.requirements if r.category == "experience")
    assert experience_req.concept_id is None
    assert experience_req.github_observability == NOT_OBS
    assert experience_req.necessity == REQUIRED  # REQUIRED but NOT scoreable from GitHub


# ---------------------------------------------------------------------------
# Cross-cutting: one generic model, three radically different jobs
# ---------------------------------------------------------------------------

def test_all_three_jobs_fit_the_same_profile_type_with_no_role_specific_schema():
    profiles = [_backend_profile(), _robotics_profile(), _ml_profile()]
    assert all(isinstance(p, JobRequirementProfile) for p in profiles)
    # Every requirement across all three jobs is a plain JobRequirement --
    # no per-role subclass, no per-role field, no role enum anywhere.
    for profile in profiles:
        for requirement in profile.requirements:
            assert isinstance(requirement, JobRequirement)


def test_python_requirement_shape_is_identical_across_backend_robotics_and_ml():
    # The exact same concept_id/type shows up in all three jobs at
    # different importance levels -- proving concepts, not role
    # templates, are what the model keys on.
    backend_python = next(r for r in _backend_profile().requirements if r.concept_id == "language.python")
    robotics_python = next(r for r in _robotics_profile().requirements if r.concept_id == "language.python")
    ml_python = next(r for r in _ml_profile().requirements if r.concept_id == "language.python")

    assert {backend_python.importance, robotics_python.importance, ml_python.importance} == {
        Importance.HIGH,
        Importance.MEDIUM,
    }
    assert backend_python.necessity == robotics_python.necessity == ml_python.necessity == REQUIRED
