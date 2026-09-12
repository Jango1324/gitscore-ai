"""Milestone 5C: gitscore.evidence.summary (CandidateConceptSummary,
summarize_concept, build_concept_summaries)."""
from gitscore.evidence import ConfidenceLevel, Evidence, EvidenceType, RepositoryIdentity
from gitscore.evidence.summary import build_concept_summaries, summarize_concept


def ev(repo="repo-a", file_path=None, obs="observation", concept="database.postgresql",
       confidence=ConfidenceLevel.MODERATE, evidence_type=EvidenceType.DEPENDENCY, owner="candidate"):
    return Evidence(
        repository=RepositoryIdentity(owner=owner, name=repo),
        evidence_type=evidence_type,
        raw_observation=obs,
        concept_id=concept,
        confidence=confidence,
        extractor_version="test@1",
        file_path=file_path,
    )


# ---------------------------------------------------------------------------
# summarize_concept
# ---------------------------------------------------------------------------

def test_no_evidence_for_a_concept_returns_none_not_an_empty_summary():
    result = summarize_concept("database.postgresql", [ev(concept="ml.framework.pytorch")])
    assert result is None


def test_single_evidence_item():
    summary = summarize_concept("database.postgresql", [ev()])
    assert summary.concept_id == "database.postgresql"
    assert summary.evidence_count == 1
    assert summary.strongest_confidence == ConfidenceLevel.MODERATE


def test_multiple_evidence_items_for_the_same_concept():
    items = [
        ev(repo="repo-a", obs="psycopg2", confidence=ConfidenceLevel.STRONG),
        ev(repo="repo-a", obs="postgres in README", evidence_type=EvidenceType.README, confidence=ConfidenceLevel.WEAK),
    ]
    summary = summarize_concept("database.postgresql", items)
    assert summary.evidence_count == 2
    assert summary.strongest_confidence == ConfidenceLevel.STRONG


def test_evidence_across_multiple_repositories_is_all_retained():
    items = [
        ev(repo="repo-a", obs="a"),
        ev(repo="repo-b", obs="b"),
        ev(repo="repo-c", obs="c"),
    ]
    summary = summarize_concept("database.postgresql", items)
    assert summary.evidence_count == 3
    assert summary.repositories == (
        RepositoryIdentity(owner="candidate", name="repo-a"),
        RepositoryIdentity(owner="candidate", name="repo-b"),
        RepositoryIdentity(owner="candidate", name="repo-c"),
    )


def test_repositories_property_deduplicates_multiple_evidence_in_the_same_repo():
    items = [ev(repo="repo-a", obs="first"), ev(repo="repo-a", obs="second")]
    summary = summarize_concept("database.postgresql", items)
    assert summary.repositories == (RepositoryIdentity(owner="candidate", name="repo-a"),)


def test_strongest_confidence_is_the_max_across_all_evidence():
    items = [
        ev(confidence=ConfidenceLevel.WEAK),
        ev(obs="stronger", confidence=ConfidenceLevel.STRONG),
        ev(obs="middle", confidence=ConfidenceLevel.MODERATE),
    ]
    summary = summarize_concept("database.postgresql", items)
    assert summary.strongest_confidence == ConfidenceLevel.STRONG


def test_ignores_evidence_for_other_concepts_when_filtering():
    items = [
        ev(concept="database.postgresql", obs="a"),
        ev(concept="ml.framework.pytorch", obs="b"),
    ]
    summary = summarize_concept("database.postgresql", items)
    assert summary.evidence_count == 1


def test_deterministic_ordering_regardless_of_input_order():
    items_forward = [ev(repo="z-repo", obs="z"), ev(repo="a-repo", obs="a")]
    items_reversed = list(reversed(items_forward))

    forward = summarize_concept("database.postgresql", items_forward)
    reversed_ = summarize_concept("database.postgresql", items_reversed)

    assert forward.evidence == reversed_.evidence


def test_exact_duplicate_evidence_collapses_to_one():
    duplicate_a = ev(repo="repo-a", obs="psycopg2")
    duplicate_b = ev(repo="repo-a", obs="psycopg2")  # structurally identical

    summary = summarize_concept("database.postgresql", [duplicate_a, duplicate_b])
    assert summary.evidence_count == 1


def test_evidence_differing_in_any_field_is_not_a_duplicate():
    same_repo_different_file = [
        ev(repo="repo-a", obs="psycopg2", file_path="requirements.txt"),
        ev(repo="repo-a", obs="psycopg2", file_path="pyproject.toml"),
    ]
    summary = summarize_concept("database.postgresql", same_repo_different_file)
    assert summary.evidence_count == 2


# ---------------------------------------------------------------------------
# build_concept_summaries
# ---------------------------------------------------------------------------

def test_build_concept_summaries_groups_by_concept():
    items = [
        ev(concept="database.postgresql", obs="a"),
        ev(concept="ml.framework.pytorch", obs="b"),
        ev(concept="database.postgresql", obs="c"),
    ]
    summaries = build_concept_summaries(items)
    assert set(summaries) == {"database.postgresql", "ml.framework.pytorch"}
    assert summaries["database.postgresql"].evidence_count == 2
    assert summaries["ml.framework.pytorch"].evidence_count == 1


def test_build_concept_summaries_of_empty_evidence_is_an_empty_dict():
    assert build_concept_summaries([]) == {}


def test_build_concept_summaries_deterministic_regardless_of_input_order():
    items = [ev(concept="database.postgresql", obs="a"), ev(concept="ml.framework.pytorch", obs="b")]
    forward = build_concept_summaries(items)
    backward = build_concept_summaries(list(reversed(items)))
    assert forward["database.postgresql"].evidence == backward["database.postgresql"].evidence
    assert forward["ml.framework.pytorch"].evidence == backward["ml.framework.pytorch"].evidence
