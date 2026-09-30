"""Milestone 6A: gitscore.jobs.profile.JobRequirementProfile."""
import dataclasses

import pytest

from gitscore.jobs import (
    GithubObservability,
    Importance,
    JobRequirement,
    JobRequirementProfile,
    Necessity,
    SourceSpan,
)
from gitscore.jobs.types import JOB_REQUIREMENT_SCHEMA_VERSION


def req(text, **overrides):
    base = dict(
        original_text=text,
        necessity=Necessity.REQUIRED,
        importance=Importance.MEDIUM,
        github_observability=GithubObservability.PARTIALLY_OBSERVABLE,
    )
    base.update(overrides)
    return JobRequirement(**base)


# ---------------------------------------------------------------------------
# Multiple / mixed requirements, ordering, description preservation
# ---------------------------------------------------------------------------

def test_profile_holds_multiple_requirements():
    r1 = req("Python", concept_id="language.python")
    r2 = req("PostgreSQL", concept_id="database.postgresql")
    profile = JobRequirementProfile(
        raw_text="Python and PostgreSQL required.",
        requirements=(r1, r2),
        parser_version="manual:v1",
    )
    assert profile.requirement_count == 2
    assert profile.requirements == (r1, r2)


def test_profile_holds_mixed_technical_and_non_technical_requirements():
    technical = req("Docker", concept_id="infra.docker")
    non_technical = req(
        "Excellent communication skills",
        concept_id=None,
        github_observability=GithubObservability.NOT_OBSERVABLE,
    )
    profile = JobRequirementProfile(
        raw_text="Docker. Excellent communication skills.",
        requirements=(technical, non_technical),
        parser_version="manual:v1",
    )
    assert profile.requirements[0].is_technical
    assert not profile.requirements[1].is_technical


def test_requirement_order_is_preserved_exactly_as_given():
    r1 = req("first")
    r2 = req("second")
    r3 = req("third")
    profile = JobRequirementProfile(
        raw_text="first second third", requirements=(r3, r1, r2), parser_version="manual:v1"
    )
    # NOT re-sorted into any canonical order -- input order survives.
    assert profile.requirements == (r3, r1, r2)


def test_original_description_text_is_preserved_verbatim():
    raw = "We are looking for a Backend Software Engineer.\nRequirements:\n- Python\n- PostgreSQL"
    profile = JobRequirementProfile(raw_text=raw, requirements=(), parser_version="manual:v1")
    assert profile.raw_text == raw


def test_optional_title_and_company_default_to_none():
    profile = JobRequirementProfile(raw_text="Python required.", requirements=(), parser_version="manual:v1")
    assert profile.title is None
    assert profile.company is None


def test_optional_title_and_company_can_be_set():
    profile = JobRequirementProfile(
        raw_text="Python required.",
        requirements=(),
        parser_version="manual:v1",
        title="Backend Software Engineer",
        company="Acme Corp",
    )
    assert profile.title == "Backend Software Engineer"
    assert profile.company == "Acme Corp"


def test_empty_requirements_tuple_is_a_valid_profile():
    profile = JobRequirementProfile(raw_text="No structured requirements yet.", requirements=(), parser_version="manual:v1")
    assert profile.requirements == ()
    assert profile.requirement_count == 0


# ---------------------------------------------------------------------------
# Necessity-partitioning helpers
# ---------------------------------------------------------------------------

def test_required_and_preferred_requirements_partition_correctly():
    required = req("Python", necessity=Necessity.REQUIRED, concept_id="language.python")
    preferred = req("Kubernetes is a plus", necessity=Necessity.PREFERRED, concept_id="unresolved:kubernetes")
    profile = JobRequirementProfile(
        raw_text="Python required. Kubernetes is a plus.",
        requirements=(required, preferred),
        parser_version="manual:v1",
    )
    assert profile.required_requirements() == (required,)
    assert profile.preferred_requirements() == (preferred,)


# ---------------------------------------------------------------------------
# Invalid states (Part 11)
# ---------------------------------------------------------------------------

def test_empty_raw_text_is_rejected():
    with pytest.raises(ValueError):
        JobRequirementProfile(raw_text="", requirements=(), parser_version="manual:v1")


def test_whitespace_only_raw_text_is_rejected():
    with pytest.raises(ValueError):
        JobRequirementProfile(raw_text="   \n  ", requirements=(), parser_version="manual:v1")


def test_empty_parser_version_is_rejected():
    with pytest.raises(ValueError):
        JobRequirementProfile(raw_text="Python required.", requirements=(), parser_version="")


def test_source_span_within_bounds_is_accepted():
    span = SourceSpan(start=0, end=6)
    requirement = req("Python", concept_id="language.python", source_span=span)
    profile = JobRequirementProfile(
        raw_text="Python required.", requirements=(requirement,), parser_version="manual:v1"
    )
    assert profile.requirements[0].source_span == span


def test_source_span_beyond_raw_text_bounds_is_rejected():
    span = SourceSpan(start=0, end=500)
    requirement = req("Python", concept_id="language.python", source_span=span)
    with pytest.raises(ValueError):
        JobRequirementProfile(
            raw_text="Python required.", requirements=(requirement,), parser_version="manual:v1"
        )


def test_exact_duplicate_requirements_are_rejected():
    duplicate = req("Python", concept_id="language.python")
    with pytest.raises(ValueError):
        JobRequirementProfile(
            raw_text="Python required. Python required.",
            requirements=(duplicate, duplicate),
            parser_version="manual:v1",
        )


def test_alternative_group_with_reordered_ids_is_an_exact_duplicate():
    # Milestone 6B.1: alternative_concept_ids is stored sorted, so
    # "Python or Go" and "Go or Python" built with otherwise-identical
    # fields (including identical original_text/span, as if the same
    # sentence were parsed twice) collide as exact duplicates -- the
    # profile-level rejection Milestone 6A already has, working for free.
    a = req("Python or Go", concept_id=None, alternative_concept_ids=("language.python", "language.go"))
    b = req("Python or Go", concept_id=None, alternative_concept_ids=("language.go", "language.python"))
    with pytest.raises(ValueError):
        JobRequirementProfile(raw_text="Python or Go required.", requirements=(a, b), parser_version="manual:v1")


def test_requirements_differing_by_source_span_are_not_duplicates():
    # Same text/claim mentioned twice in a posting at two different
    # locations is NOT a structural duplicate.
    r1 = req("Python", concept_id="language.python", source_span=SourceSpan(0, 6))
    r2 = req("Python", concept_id="language.python", source_span=SourceSpan(20, 26))
    profile = JobRequirementProfile(
        raw_text="Python required. Also: Python again.",
        requirements=(r1, r2),
        parser_version="manual:v1",
    )
    assert profile.requirement_count == 2


# ---------------------------------------------------------------------------
# Candidate-independence (mirrors CandidateEvidenceProfile's own pinned test)
# ---------------------------------------------------------------------------

def test_profile_has_no_candidate_or_match_fields():
    profile = JobRequirementProfile(raw_text="Python required.", requirements=(), parser_version="manual:v1")
    field_names = {f.name for f in dataclasses.fields(profile)}
    forbidden = {
        "candidate", "candidate_id", "username", "evidence", "evidence_profile",
        "match_score", "coverage_score", "strengths", "gaps", "repositories",
        "repository_references", "alternative_roles",
    }
    assert field_names.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# Immutability / hashing
# ---------------------------------------------------------------------------

def test_profile_is_frozen():
    profile = JobRequirementProfile(raw_text="Python required.", requirements=(), parser_version="manual:v1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        profile.title = "Something Else"


def test_profile_is_hashable():
    p1 = JobRequirementProfile(raw_text="Python required.", requirements=(), parser_version="manual:v1")
    p2 = JobRequirementProfile(raw_text="Python required.", requirements=(), parser_version="manual:v1")
    assert p1 == p2
    assert hash(p1) == hash(p2)


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

def test_schema_version_is_stamped_by_default():
    profile = JobRequirementProfile(raw_text="Python required.", requirements=(), parser_version="manual:v1")
    assert profile.schema_version == JOB_REQUIREMENT_SCHEMA_VERSION


def test_job_requirement_schema_version_constant():
    # Bumped to 2 in Milestone 6B.1: JobRequirement gained
    # alternative_concept_ids (a genuine shape change) -- see
    # jobs/types.py's versioning policy and docs/CHANGELOG_DEV.md's
    # Milestone 6B.1 entry.
    assert isinstance(JOB_REQUIREMENT_SCHEMA_VERSION, int)
    assert JOB_REQUIREMENT_SCHEMA_VERSION == 2
