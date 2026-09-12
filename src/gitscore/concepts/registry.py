"""Milestone 5C -- the technical concept registry and resolver.

A SMALL, REPRESENTATIVE set of concepts proving the mechanism, not a
complete ontology (per the Milestone 5C instructions: "the important
thing is the mechanism, not the number of concepts"). Adding a new
concept is adding one entry to _CONCEPTS below -- no change to
normalize.py, ConceptRegistry, or resolve_concept.

Bump CONCEPT_REGISTRY_VERSION whenever:
  - a concept is added, renamed, or merged/deprecated, or
  - normalize.py's normalization rules change (that changes which
    aliases resolve).
Never touch SCORING_RUBRIC_VERSION, DATASET_VERSION (dataset/schema.py),
or REPOSITORY_RANKING_VERSION (ranking/config.py) for any of this --
this registry is an independent concern.

The registry is built ONCE at import time and never mutated afterward.
Unknown terms (see resolve_concept) are represented explicitly; they are
never written into this registry (architectural rule: no dynamic
registry mutation from unrecognized input).
"""
from __future__ import annotations

from dataclasses import dataclass

from gitscore.concepts.models import TechnicalConcept
from gitscore.concepts.normalize import normalize_term

CONCEPT_REGISTRY_VERSION = 1

# A small, representative registry spanning several categories -- proves
# the mechanism (data-driven, no if/elif ladder) without building a full
# ontology. Aliases are the raw, human-typed forms; normalize_term()
# is applied to them (and to lookup terms) before comparison, so an
# alias here does not need to already be lowercase/punctuation-free.
_CONCEPTS: tuple[TechnicalConcept, ...] = (
    TechnicalConcept(
        concept_id="language.python",
        display_name="Python",
        category="language",
        aliases=("python", "python3"),
    ),
    TechnicalConcept(
        concept_id="database.postgresql",
        display_name="PostgreSQL",
        category="database",
        aliases=("postgresql", "postgres", "psql", "psycopg2"),
    ),
    TechnicalConcept(
        concept_id="database.redis",
        display_name="Redis",
        category="database",
        aliases=("redis",),
    ),
    TechnicalConcept(
        concept_id="ml.framework.pytorch",
        display_name="PyTorch",
        category="ml_framework",
        aliases=("pytorch", "torch"),
    ),
    TechnicalConcept(
        concept_id="framework.react",
        display_name="React",
        category="frontend_framework",
        aliases=("react", "react.js", "reactjs"),
    ),
    TechnicalConcept(
        concept_id="framework.nextjs",
        display_name="Next.js",
        category="frontend_framework",
        aliases=("next", "next.js", "nextjs"),
    ),
    TechnicalConcept(
        concept_id="infra.docker",
        display_name="Docker",
        category="infrastructure",
        aliases=("docker", "dockerfile"),
    ),
    TechnicalConcept(
        concept_id="cloud.aws",
        display_name="AWS",
        category="cloud",
        aliases=("aws", "amazon web services"),
    ),
    TechnicalConcept(
        concept_id="platform.cuda",
        display_name="CUDA",
        category="platform",
        aliases=("cuda",),
    ),
    TechnicalConcept(
        concept_id="robotics.ros2",
        display_name="ROS2",
        category="robotics",
        aliases=("ros2", "ros 2"),
    ),
    TechnicalConcept(
        concept_id="embedded.rtos.freertos",
        display_name="FreeRTOS",
        category="embedded",
        aliases=("freertos",),
        parent_id="embedded.rtos",
    ),
    TechnicalConcept(
        concept_id="hdl.verilog",
        display_name="Verilog",
        category="hardware_description",
        aliases=("verilog",),
    ),
    TechnicalConcept(
        concept_id="toolchain.llvm",
        display_name="LLVM",
        category="compiler_toolchain",
        aliases=("llvm",),
    ),
)


class ConceptRegistry:
    """An immutable, in-memory index over a fixed set of TechnicalConcepts.

    Built once at construction; never mutated afterward.
    """

    def __init__(self, concepts):
        self._by_id = {concept.concept_id: concept for concept in concepts}
        self._by_normalized_alias: dict[str, TechnicalConcept] = {}
        for concept in concepts:
            for alias in concept.aliases:
                self._by_normalized_alias[normalize_term(alias)] = concept

    def get(self, concept_id: str) -> TechnicalConcept | None:
        return self._by_id.get(concept_id)

    def lookup_by_normalized_alias(self, normalized_alias: str) -> TechnicalConcept | None:
        return self._by_normalized_alias.get(normalized_alias)

    def all_concepts(self) -> tuple[TechnicalConcept, ...]:
        return tuple(self._by_id.values())


_DEFAULT_REGISTRY = ConceptRegistry(_CONCEPTS)


def default_registry() -> ConceptRegistry:
    """The shared, immutable default registry instance."""
    return _DEFAULT_REGISTRY


_UNRESOLVED_PREFIX = "unresolved:"


def unresolved_concept_id(term: str) -> str:
    """A deterministic pseudo-concept-id for a term with no registry match.

    The SAME literal term always produces the SAME unresolved id (useful
    later for tallying which unknown terms show up most, for registry
    curation) -- but two differently-spelled unknown terms referring to
    the same real thing are NOT merged. That would require exactly the
    fuzzy-matching/ontology-building work this milestone is scoped to
    avoid.
    """
    return _UNRESOLVED_PREFIX + normalize_term(term).replace(" ", "_")


def is_unresolved_concept_id(concept_id: str) -> bool:
    return concept_id.startswith(_UNRESOLVED_PREFIX)


@dataclass(frozen=True)
class ConceptResolution:
    """The outcome of resolving one raw term against the registry.

    `matched` is the explicit, checkable result Milestone 5C Part 3
    asks for. `concept_id` is always populated regardless of `matched`
    -- callers that just need an id to attach to an Evidence record
    never have to branch on `matched` themselves (see
    is_unresolved_concept_id() when they do need to check).
    """

    raw_term: str
    normalized_term: str
    matched: bool
    concept: TechnicalConcept | None

    @property
    def concept_id(self) -> str:
        if self.matched:
            return self.concept.concept_id
        return unresolved_concept_id(self.raw_term)


def resolve_concept(term: str, registry: ConceptRegistry | None = None) -> ConceptResolution:
    """Resolve one raw term to a TechnicalConcept, deterministically.

    No LLM, no fuzzy matching -- exact match against normalized aliases
    only (Milestone 5C Part 3: "Normalization must NOT use an LLM").
    An unmatched term is never dropped and never written into the
    registry -- see ConceptResolution.concept_id / unresolved_concept_id.
    """
    registry = registry or default_registry()
    normalized = normalize_term(term)
    concept = registry.lookup_by_normalized_alias(normalized)
    return ConceptResolution(
        raw_term=term,
        normalized_term=normalized,
        matched=concept is not None,
        concept=concept,
    )
