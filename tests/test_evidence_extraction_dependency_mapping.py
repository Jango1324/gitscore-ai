"""Milestone 5D -- gitscore.evidence.extraction.dependency_evidence.

Covers the centralized package -> concept resolution shared by every
manifest extractor, independent of any one file format.
"""
from gitscore.evidence.extraction.dependency_evidence import (
    DependencyDeclaration,
    declarations_to_evidence,
)
from gitscore.evidence.types import ConfidenceLevel, EvidenceType


def test_known_package_resolves_to_its_concept_with_strong_confidence():
    declarations = [DependencyDeclaration(package_name="torch", raw_text="torch==2.5")]

    evidence, unknown = declarations_to_evidence(
        "octocat", "repo", declarations, file_path="requirements.txt", extractor_version="requirements:v1"
    )

    assert unknown == []
    assert len(evidence) == 1
    item = evidence[0]
    assert item.concept_id == "ml.framework.pytorch"
    assert item.confidence == ConfidenceLevel.STRONG
    assert item.evidence_type == EvidenceType.DEPENDENCY
    assert item.file_path == "requirements.txt"
    assert item.raw_observation == "torch==2.5"


def test_package_alias_that_differs_from_display_name_resolves_correctly():
    # psycopg2-binary is an alias of database.postgresql, not its own concept.
    declarations = [DependencyDeclaration(package_name="psycopg2-binary", raw_text="psycopg2-binary")]

    evidence, unknown = declarations_to_evidence(
        "octocat", "repo", declarations, file_path="requirements.txt", extractor_version="requirements:v1"
    )

    assert unknown == []
    assert evidence[0].concept_id == "database.postgresql"


def test_unknown_package_is_tracked_as_a_diagnostic_not_turned_into_evidence():
    declarations = [DependencyDeclaration(package_name="some-made-up-thing", raw_text="some-made-up-thing")]

    evidence, unknown = declarations_to_evidence(
        "octocat", "repo", declarations, file_path="requirements.txt", extractor_version="requirements:v1"
    )

    assert evidence == []
    assert unknown == ["some-made-up-thing"]


def test_mixed_known_and_unknown_packages_split_correctly():
    declarations = [
        DependencyDeclaration(package_name="torch", raw_text="torch"),
        DependencyDeclaration(package_name="some-made-up-thing", raw_text="some-made-up-thing"),
        DependencyDeclaration(package_name="fastapi", raw_text="fastapi"),
    ]

    evidence, unknown = declarations_to_evidence(
        "octocat", "repo", declarations, file_path="requirements.txt", extractor_version="requirements:v1"
    )

    assert {item.concept_id for item in evidence} == {"ml.framework.pytorch", "framework.fastapi"}
    assert unknown == ["some-made-up-thing"]


def test_next_package_still_resolves_to_nextjs_despite_being_readme_unsafe():
    # Milestone 5D.1 regression guard: "next" is excluded from
    # README-prose matching (readme_unsafe_aliases), but a structured
    # dependency declaration is unambiguous by construction and must
    # keep resolving via the full resolve_concept() alias set.
    declarations = [DependencyDeclaration(package_name="next", raw_text='"next": "^14.0.0"')]

    evidence, unknown = declarations_to_evidence(
        "octocat", "repo", declarations, file_path="package.json", extractor_version="npm:v1"
    )

    assert unknown == []
    assert evidence[0].concept_id == "framework.nextjs"


def test_empty_declarations_produce_no_evidence_and_no_unknowns():
    evidence, unknown = declarations_to_evidence(
        "octocat", "repo", [], file_path="requirements.txt", extractor_version="requirements:v1"
    )
    assert evidence == []
    assert unknown == []
