"""Milestone 5D -- gitscore.evidence.extraction.languages."""
from gitscore.evidence.extraction.languages import (
    EXTRACTOR_VERSION,
    MIN_SIGNIFICANT_PERCENTAGE,
    MODERATE_CONFIDENCE_PERCENTAGE,
    evidence_from_languages,
)
from gitscore.evidence.types import ConfidenceLevel, EvidenceType


def test_recognized_language_produces_resolved_evidence():
    evidence = evidence_from_languages("octocat", "repo", {"Python": 1000})

    assert len(evidence) == 1
    item = evidence[0]
    assert item.repository.owner == "octocat"
    assert item.repository.name == "repo"
    assert item.concept_id == "language.python"
    assert item.evidence_type == EvidenceType.REPOSITORY_LANGUAGE
    assert item.extractor_version == EXTRACTOR_VERSION
    assert item.is_resolved


def test_multiple_meaningful_languages_each_produce_evidence():
    evidence = evidence_from_languages("octocat", "repo", {"Python": 6000, "C++": 4000})

    concept_ids = {item.concept_id for item in evidence}
    assert concept_ids == {"language.python", "language.cpp"}


def test_tiny_incidental_language_is_filtered_out():
    # Python 9990 bytes (99.9%), Shell 10 bytes (0.1%) -- well under the
    # significance floor.
    evidence = evidence_from_languages("octocat", "repo", {"Python": 9990, "Shell": 10})

    concept_ids = {item.concept_id for item in evidence}
    assert concept_ids == {"language.python"}


def test_unknown_meaningful_language_follows_unresolved_policy():
    evidence = evidence_from_languages("octocat", "repo", {"COBOL": 5000})

    assert len(evidence) == 1
    assert evidence[0].concept_id == "unresolved:cobol"
    assert not evidence[0].is_resolved


def test_empty_language_response_produces_no_evidence():
    assert evidence_from_languages("octocat", "repo", {}) == []


def test_short_readme_unsafe_aliases_still_resolve_githubs_exact_language_names():
    # Milestone 5D.1 regression guard: "go", "js"/"ts" (via javascript/
    # typescript), and bare "c" were marked readme_unsafe_aliases for
    # free-form README matching, but GitHub's own language-stats names
    # ("Go", "JavaScript", "TypeScript", "C", "C++") must keep resolving
    # exactly as before through resolve_concept()'s full alias set --
    # language-stats extraction never calls readme_safe_aliases().
    evidence = evidence_from_languages(
        "octocat",
        "repo",
        {"Go": 2000, "JavaScript": 2000, "TypeScript": 2000, "C": 2000, "C++": 2000},
    )
    concept_ids = {item.concept_id for item in evidence}
    assert concept_ids == {
        "language.go",
        "language.javascript",
        "language.typescript",
        "language.c",
        "language.cpp",
    }
    assert all(item.is_resolved for item in evidence)


def test_dominant_language_gets_moderate_confidence_minor_gets_weak():
    # Python 45% (above the 40% MODERATE_CONFIDENCE_PERCENTAGE floor),
    # Go 5.5% (above the 5% significance floor but below MODERATE), Rust
    # 0.01% (below the significance floor entirely).
    evidence = evidence_from_languages(
        "octocat", "repo", {"Python": 4500, "Go": 550, "Rust": 1, "PHP": 4949}
    )
    by_concept = {item.concept_id: item for item in evidence}

    assert MIN_SIGNIFICANT_PERCENTAGE < 5.5
    assert MODERATE_CONFIDENCE_PERCENTAGE == 40.0
    assert by_concept["language.python"].confidence == ConfidenceLevel.MODERATE
    assert by_concept["language.go"].confidence == ConfidenceLevel.WEAK
    assert "language.rust" not in by_concept
