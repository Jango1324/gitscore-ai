"""Milestone 5C: gitscore.evidence.models (RepositoryIdentity, Evidence)."""
import dataclasses

import pytest

from gitscore.evidence import ConfidenceLevel, Evidence, EvidenceType, RepositoryIdentity
from gitscore.evidence.types import EVIDENCE_SCHEMA_VERSION


def make_evidence(**overrides):
    base = dict(
        repository=RepositoryIdentity(owner="candidate", name="backend-api"),
        evidence_type=EvidenceType.DEPENDENCY,
        raw_observation="psycopg2",
        concept_id="database.postgresql",
        confidence=ConfidenceLevel.STRONG,
        extractor_version="test@1",
    )
    base.update(overrides)
    return Evidence(**base)


# ---------------------------------------------------------------------------
# Required provenance
# ---------------------------------------------------------------------------

def test_required_provenance_fields_are_present():
    evidence = make_evidence()
    assert evidence.repository == RepositoryIdentity(owner="candidate", name="backend-api")
    assert evidence.evidence_type == EvidenceType.DEPENDENCY
    assert evidence.raw_observation == "psycopg2"
    assert evidence.concept_id == "database.postgresql"
    assert evidence.confidence == ConfidenceLevel.STRONG
    assert evidence.extractor_version == "test@1"


def test_file_path_is_optional_and_defaults_to_none():
    evidence = make_evidence()
    assert evidence.file_path is None

    with_file = make_evidence(file_path="requirements.txt")
    assert with_file.file_path == "requirements.txt"


def test_location_and_collected_at_are_optional():
    evidence = make_evidence()
    assert evidence.location is None
    assert evidence.collected_at is None


# ---------------------------------------------------------------------------
# Confidence semantics: claim strength, NOT skill
# ---------------------------------------------------------------------------

def test_confidence_levels_are_ordered():
    assert ConfidenceLevel.WEAK < ConfidenceLevel.MODERATE < ConfidenceLevel.STRONG


def test_confidence_has_exactly_three_ordinal_levels():
    assert {c.name for c in ConfidenceLevel} == {"WEAK", "MODERATE", "STRONG"}


# ---------------------------------------------------------------------------
# Resolved vs. unresolved concept_id
# ---------------------------------------------------------------------------

def test_is_resolved_true_for_a_real_concept_id():
    evidence = make_evidence(concept_id="database.postgresql")
    assert evidence.is_resolved is True


def test_is_resolved_false_for_an_unresolved_placeholder():
    evidence = make_evidence(concept_id="unresolved:some-new-framework")
    assert evidence.is_resolved is False


# ---------------------------------------------------------------------------
# Immutability / stability
# ---------------------------------------------------------------------------

def test_repository_identity_is_frozen():
    identity = RepositoryIdentity(owner="candidate", name="repo")
    with pytest.raises(dataclasses.FrozenInstanceError):
        identity.owner = "someone-else"


def test_evidence_is_frozen():
    evidence = make_evidence()
    with pytest.raises(dataclasses.FrozenInstanceError):
        evidence.confidence = ConfidenceLevel.WEAK


def test_evidence_is_hashable_and_supports_set_dedup():
    a = make_evidence()
    b = make_evidence()  # structurally identical
    c = make_evidence(raw_observation="different-observation")

    assert a == b
    assert hash(a) == hash(b)
    assert len({a, b, c}) == 2


def test_repository_identity_equality_is_structural():
    assert RepositoryIdentity(owner="u", name="r") == RepositoryIdentity(owner="u", name="r")
    assert RepositoryIdentity(owner="u", name="r") != RepositoryIdentity(owner="u", name="other")


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

def test_evidence_schema_version_constant_exists():
    # Bumped to 2 in Milestone 5D: RepositoryAnalysisCoverage gained the
    # additive `partially_analyzed` field (a real SHAPE change) to
    # represent "attempted but a source could not be inspected" --
    # see evidence/profile.py's docstring and docs/CHANGELOG_DEV.md's
    # Milestone 5D entry.
    assert isinstance(EVIDENCE_SCHEMA_VERSION, int)
    assert EVIDENCE_SCHEMA_VERSION == 2
