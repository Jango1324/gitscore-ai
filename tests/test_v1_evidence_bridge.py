"""Milestone 5C Part 10: demonstrate that information the EXISTING V1
pipeline already produces can be represented as Evidence, without
changing features/ml.py, features/readme.py, features/languages.py, or
scoring/readiness.py in any way.

This module imports gitscore.evidence.v1_bridge (demonstration-only, not
wired into pipeline/analyze.py) and gitscore.github.parser's real
parse_repo()/parse_repo_summary() shapes via the existing conftest.py
fixtures -- proving compatibility, not migrating V1.
"""
from conftest import make_repo

from gitscore.evidence.types import ConfidenceLevel, EvidenceType
from gitscore.evidence.v1_bridge import (
    evidence_from_readme_text,
    evidence_from_repository_language,
    evidence_from_topics,
)


# ---------------------------------------------------------------------------
# repository primary language = Python
# ---------------------------------------------------------------------------

def test_v1_primary_language_becomes_weak_repository_language_evidence():
    repo = make_repo(name="my-project", primary_language="Python")

    evidence = evidence_from_repository_language("candidate", repo)

    assert len(evidence) == 1
    item = evidence[0]
    assert item.evidence_type == EvidenceType.REPOSITORY_LANGUAGE
    assert item.concept_id == "language.python"
    assert item.confidence == ConfidenceLevel.WEAK
    assert item.repository.owner == "candidate"
    assert item.repository.name == "my-project"


def test_v1_unrecognized_primary_language_is_not_silently_dropped():
    # "COBOL" is outside the small Milestone 5C registry -- must still
    # produce Evidence, with an unresolved concept_id, never nothing.
    repo = make_repo(name="legacy-system", primary_language="COBOL")

    evidence = evidence_from_repository_language("candidate", repo)

    assert len(evidence) == 1
    assert evidence[0].is_resolved is False
    assert evidence[0].concept_id == "unresolved:cobol"


def test_v1_repo_with_no_primary_language_produces_no_language_evidence():
    repo = make_repo(name="empty-repo", primary_language=None)
    assert evidence_from_repository_language("candidate", repo) == []


# ---------------------------------------------------------------------------
# README metadata says PyTorch / ROS2
# ---------------------------------------------------------------------------

def test_v1_readme_mentioning_a_known_concept_becomes_moderate_readme_evidence():
    repo = make_repo(name="robotics-project", readme="This project is built using ROS2 for navigation.")

    evidence = evidence_from_readme_text("candidate", repo)

    assert len(evidence) == 1
    item = evidence[0]
    assert item.evidence_type == EvidenceType.README
    assert item.concept_id == "robotics.ros2"
    assert item.confidence == ConfidenceLevel.MODERATE
    assert item.file_path == "README.md"


def test_v1_readme_mentioning_multiple_concepts_produces_one_evidence_item_each():
    repo = make_repo(name="ml-robot", readme="Uses PyTorch for perception and ROS2 for control.")

    evidence = evidence_from_readme_text("candidate", repo)
    concept_ids = {item.concept_id for item in evidence}

    assert concept_ids == {"ml.framework.pytorch", "robotics.ros2"}


def test_v1_readme_with_no_recognized_concept_produces_no_evidence():
    repo = make_repo(name="mystery-project", readme="A collection of personal notes and ideas.")
    assert evidence_from_readme_text("candidate", repo) == []


def test_v1_repo_with_no_readme_produces_no_evidence():
    repo = make_repo(name="no-readme", readme=None)
    assert evidence_from_readme_text("candidate", repo) == []


# ---------------------------------------------------------------------------
# repository metadata (topics)
# ---------------------------------------------------------------------------

def test_v1_matching_topic_becomes_weak_repository_metadata_evidence():
    evidence = evidence_from_topics("candidate", "backend-api", ["postgresql", "python"])

    concept_ids = {item.concept_id for item in evidence}
    assert concept_ids == {"database.postgresql", "language.python"}
    assert all(item.evidence_type == EvidenceType.REPOSITORY_METADATA for item in evidence)
    assert all(item.confidence == ConfidenceLevel.WEAK for item in evidence)


def test_v1_non_technical_topics_are_skipped_not_turned_into_unresolved_evidence():
    evidence = evidence_from_topics("candidate", "portfolio-site", ["hacktoberfest", "portfolio"])
    assert evidence == []


def test_v1_no_topics_produces_no_evidence():
    assert evidence_from_topics("candidate", "repo", []) == []
    assert evidence_from_topics("candidate", "repo", None) == []
