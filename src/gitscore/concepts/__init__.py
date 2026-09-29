"""Milestone 5C -- normalized technical concepts and their registry.

See docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md Part 8 and
docs/ARCHITECTURE.md's Milestone 5C section for the architectural
context. This package has no dependency on gitscore.evidence,
gitscore.ranking, the database, or any job-related module.
"""
from gitscore.concepts.models import TechnicalConcept
from gitscore.concepts.normalize import normalize_term
from gitscore.concepts.registry import (
    CONCEPT_REGISTRY_VERSION,
    ConceptRegistry,
    ConceptResolution,
    default_registry,
    is_unresolved_concept_id,
    is_valid_concept_id,
    resolve_concept,
    unresolved_concept_id,
)

__all__ = [
    "CONCEPT_REGISTRY_VERSION",
    "ConceptRegistry",
    "ConceptResolution",
    "TechnicalConcept",
    "default_registry",
    "is_unresolved_concept_id",
    "is_valid_concept_id",
    "normalize_term",
    "resolve_concept",
    "unresolved_concept_id",
]
