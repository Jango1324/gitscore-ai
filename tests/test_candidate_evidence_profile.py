"""Milestone 5C: gitscore.evidence.profile (CandidateEvidenceProfile,
RepositoryAnalysisCoverage, build_candidate_evidence_profile)."""
import dataclasses

from gitscore.concepts import CONCEPT_REGISTRY_VERSION
from gitscore.evidence import (
    ConfidenceLevel,
    Evidence,
    EvidenceType,
    RepositoryIdentity,
    build_candidate_evidence_profile,
)
from gitscore.evidence.types import EVIDENCE_SCHEMA_VERSION


def repo(name, owner="candidate"):
    return RepositoryIdentity(owner=owner, name=name)


def ev(repo_name, concept, owner="candidate", obs="observation", confidence=ConfidenceLevel.MODERATE):
    return Evidence(
        repository=repo(repo_name, owner),
        evidence_type=EvidenceType.DEPENDENCY,
        raw_observation=obs,
        concept_id=concept,
        confidence=confidence,
        extractor_version="test@1",
    )


# ---------------------------------------------------------------------------
# Empty profile
# ---------------------------------------------------------------------------

def test_empty_profile_has_no_evidence_and_no_concepts():
    profile = build_candidate_evidence_profile("candidate", discovered=[], analyzed=[], evidence_items=[])
    assert profile.evidence == ()
    assert profile.concept_summaries == {}
    assert profile.concept("anything") is None


def test_empty_profile_still_stamps_versions():
    profile = build_candidate_evidence_profile("candidate", discovered=[], analyzed=[], evidence_items=[])
    assert profile.evidence_schema_version == EVIDENCE_SCHEMA_VERSION
    assert profile.concept_registry_version == CONCEPT_REGISTRY_VERSION


# ---------------------------------------------------------------------------
# One / multiple concepts
# ---------------------------------------------------------------------------

def test_one_concept():
    profile = build_candidate_evidence_profile(
        "candidate", discovered=[repo("r1")], analyzed=[repo("r1")],
        evidence_items=[ev("r1", "database.postgresql")],
    )
    assert set(profile.concept_summaries) == {"database.postgresql"}
    assert profile.concept("database.postgresql").evidence_count == 1


def test_multiple_concepts():
    profile = build_candidate_evidence_profile(
        "candidate", discovered=[repo("r1")], analyzed=[repo("r1")],
        evidence_items=[
            ev("r1", "database.postgresql"),
            ev("r1", "ml.framework.pytorch"),
            ev("r1", "infra.docker"),
        ],
    )
    assert set(profile.concept_summaries) == {"database.postgresql", "ml.framework.pytorch", "infra.docker"}


def test_concept_lookup_for_a_concept_with_no_evidence_returns_none():
    profile = build_candidate_evidence_profile(
        "candidate", discovered=[repo("r1")], analyzed=[repo("r1")],
        evidence_items=[ev("r1", "database.postgresql")],
    )
    assert profile.concept("ml.framework.pytorch") is None


# ---------------------------------------------------------------------------
# Discovered vs. analyzed coverage
# ---------------------------------------------------------------------------

def test_discovered_and_analyzed_counts_distinguish_full_from_partial_coverage():
    discovered = [repo(f"r{i}") for i in range(1140)]
    analyzed = discovered[:15]

    profile = build_candidate_evidence_profile(
        "candidate", discovered=discovered, analyzed=analyzed, evidence_items=[]
    )

    assert profile.coverage.discovered_count == 1140
    assert profile.coverage.analyzed_count == 15
    assert profile.coverage.is_complete is False


def test_full_coverage_when_analyzed_equals_discovered():
    repos = [repo("r1"), repo("r2")]
    profile = build_candidate_evidence_profile(
        "candidate", discovered=repos, analyzed=repos, evidence_items=[]
    )
    assert profile.coverage.is_complete is True


def test_zero_repositories_is_trivially_complete():
    profile = build_candidate_evidence_profile("candidate", discovered=[], analyzed=[], evidence_items=[])
    assert profile.coverage.is_complete is True


# ---------------------------------------------------------------------------
# partially_analyzed (Milestone 5D)
# ---------------------------------------------------------------------------


def test_partially_analyzed_defaults_to_empty():
    repos = [repo("r1")]
    profile = build_candidate_evidence_profile("candidate", discovered=repos, analyzed=repos, evidence_items=[])
    assert profile.coverage.partially_analyzed == ()
    assert profile.coverage.partially_analyzed_count == 0


def test_partially_analyzed_is_a_subset_reported_separately_from_analyzed():
    repos = [repo("r1"), repo("r2")]
    profile = build_candidate_evidence_profile(
        "candidate",
        discovered=repos,
        analyzed=repos,
        evidence_items=[],
        partially_analyzed=[repo("r1")],
    )

    assert profile.coverage.partially_analyzed_count == 1
    assert profile.coverage.partially_analyzed[0].name == "r1"
    # A partial failure does not demote the repo out of `analyzed`, and
    # does not change `is_complete` (which only compares discovered vs.
    # analyzed counts).
    assert profile.coverage.analyzed_count == 2
    assert profile.coverage.is_complete is True


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_concept_summaries_are_deterministic_regardless_of_evidence_order():
    items = [ev("r1", "database.postgresql", obs="a"), ev("r2", "ml.framework.pytorch", obs="b")]

    forward = build_candidate_evidence_profile("candidate", [repo("r1"), repo("r2")], [repo("r1"), repo("r2")], items)
    backward = build_candidate_evidence_profile(
        "candidate", [repo("r1"), repo("r2")], [repo("r1"), repo("r2")], list(reversed(items))
    )

    assert forward.evidence == backward.evidence
    assert dict(forward.concept_summaries) == dict(backward.concept_summaries)


def test_duplicate_evidence_across_the_whole_profile_collapses():
    duplicate = ev("r1", "database.postgresql", obs="psycopg2")
    profile = build_candidate_evidence_profile(
        "candidate", [repo("r1")], [repo("r1")], [duplicate, duplicate]
    )
    assert len(profile.evidence) == 1


# ---------------------------------------------------------------------------
# Job-independence (architectural rule 8)
# ---------------------------------------------------------------------------

def test_profile_has_no_job_related_fields():
    field_names = {f.name for f in dataclasses.fields(build_candidate_evidence_profile(
        "candidate", [], [], []
    ))}
    forbidden = {"job", "job_id", "target_job", "match_score", "required_skills",
                 "preferred_skills", "alternative_roles", "role"}
    assert field_names.isdisjoint(forbidden)


def test_concept_summaries_is_read_only():
    profile = build_candidate_evidence_profile(
        "candidate", [repo("r1")], [repo("r1")], [ev("r1", "database.postgresql")]
    )
    try:
        profile.concept_summaries["injected"] = "not allowed"
        assert False, "concept_summaries must not be externally mutable"
    except TypeError:
        pass
