"""Milestone 5C -- evidence type & confidence-level enums.

EVIDENCE_SCHEMA_VERSION bumps when Evidence, CandidateConceptSummary,
CandidateEvidenceProfile, or RepositoryAnalysisCoverage change SHAPE
(fields added/removed/retyped). It does NOT bump for adding a new
EvidenceType member (additive, non-breaking) or for a new concept in
the registry (that's concepts.registry.CONCEPT_REGISTRY_VERSION).
"""
from __future__ import annotations

from enum import Enum, IntEnum

EVIDENCE_SCHEMA_VERSION = 1


class EvidenceType(str, Enum):
    """Where an observation came from.

    Not every member has an extractor yet -- Milestone 5C is the domain
    model only. The enum anticipates Milestone 5D+ extractors so
    Evidence's shape does not need to change when they arrive.
    """

    REPOSITORY_LANGUAGE = "repository_language"
    REPOSITORY_METADATA = "repository_metadata"
    README = "readme"
    DEPENDENCY = "dependency"
    SOURCE_IMPORT = "source_import"
    CONFIG = "config"
    DOCKER = "docker"
    CI = "ci"
    TEST = "test"
    NOTEBOOK = "notebook"
    DEPLOYMENT = "deployment"


class ConfidenceLevel(IntEnum):
    """Ordinal confidence in the EVIDENCE CLAIM ITSELF.

    E.g. "how sure are we that this text really means PyTorch is a
    dependency" -- this is NOT candidate skill, proficiency, years of
    experience, or job fit (see docs/ARCHITECTURE.md's Milestone 5C
    section). A `requirements.txt` line containing "torch" is HIGH
    confidence that PyTorch is a declared dependency; it says nothing
    about how skilled the candidate is with it.

    An ordinal enum, not a float, on purpose: nothing in this milestone
    calibrates a claim like "0.87 confident" against any real ground
    truth, and a float would imply a precision that doesn't exist yet.
    IntEnum keeps it comparable/orderable, so "the strongest evidence
    for this concept" is a plain max() over a set of Evidence.
    """

    WEAK = 1
    MODERATE = 2
    STRONG = 3
