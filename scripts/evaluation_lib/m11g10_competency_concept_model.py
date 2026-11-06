"""Milestone 11-G10 -- a minimal, versioned CompetencyConcept data model.

Evaluation-only, exactly like `m11g9_competency_extraction_v3.py` before
it. Nothing in `src/gitscore` imports this module; it never constructs a
`Qualification`, never calls `project_qualification()`, never touches
`matching.engine`/`matching.support`, and never mutates
`gitscore.concepts.registry` or `competency_aliases.py`. Confirmed by
`tests/test_m11g10_competency_concept_model.py`, not merely intended.

## Why this module exists (Phase 1 audit, condensed -- full writeup in
docs/evaluation/MILESTONE_11_G10_COMPETENCY_CONCEPT_MODEL.md)

Two existing, independent concept vocabularies already exist in
production:

1. `gitscore.concepts.registry.TechnicalConcept` -- concrete, registered
   technologies (`concept_id` like `"infra.kubernetes"`). Already has
   `parent_id`/`related_ids`, but UNTYPED (no distinction between
   "broader" and "merely associated") and, critically, NEVER CONSUMED by
   `matching.engine`/`matching.support` -- the live matcher does exact
   `concept_id` lookup only. Today's Docker-does-not-prove-Kubernetes
   safety is true BY OMISSION (nothing traverses those fields), not by
   an enforced rule.
2. `gitscore.jobs.parsing.competency_aliases.AliasRelation` -- a
   PHRASE-TO-TAG relation (how a raw sentence phrase relates to ONE
   canonical `competency_tag`), never a TAG-TO-TAG or
   TAG-TO-`concept_id` relation. No edge between, say, `"distributed-
   systems"` and `"infra.kubernetes"` exists anywhere.

`gitscore.jobs.parsing.qualification.NormalizedReference` already keeps
these two namespaces cleanly separate (`concept_id` XOR `competency_tag`,
enforced by its own `__post_init__`) -- deliberately never merged. This
module does not merge them either. It adds exactly the missing
connective tissue: a small, versioned, OFFLINE graph that can hold a
TYPED relation between two `ConceptRef`s drawn from EITHER namespace,
without changing either namespace's own shape.

## What this module explicitly does NOT do

No necessity, no evidence, no scoring, no alignment, no transitive
inference, no automatic equivalence/satisfaction claim. See
`ConceptRelationType` and `CompetencyConceptGraph.lookup_relation()`
docstrings for exactly which safety invariants this is Enforcing, and
`docs/evaluation/MILESTONE_11_G10_COMPETENCY_CONCEPT_MODEL.md` Phase 3
for the full, named list this module was built against.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT / "src", _REPO_ROOT / "scripts" / "evaluation_lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from gitscore.concepts.registry import is_valid_concept_id  # noqa: E402
from gitscore.jobs.parsing.competency_aliases import ALL_ALIASES  # noqa: E402
from gitscore.jobs.parsing.competency_extraction import (  # noqa: E402
    _COMPETENCY_OBSERVABILITY,
)
from gitscore.jobs.parsing.observability import (  # noqa: E402
    TECHNICAL_DEFAULT_OBSERVABILITY,
)
from gitscore.jobs.parsing.qualification import NormalizedReference  # noqa: E402
from gitscore.jobs.types import GithubObservability  # noqa: E402

COMPETENCY_CONCEPT_MODEL_VERSION = 1
"""Independent of `CONCEPT_REGISTRY_VERSION` (4) and
`JOB_REQUIREMENT_SCHEMA_VERSION` (2) -- this is a THIRD, offline-only
versioning axis, mirroring the project's own existing per-subsystem
versioning convention (registry.py's own docstring: "Never touch
SCORING_RUBRIC_VERSION... this registry is an independent concern.").
Bump whenever `ConceptRef`, `CompetencyConceptNode`, or `ConceptRelation`
change SHAPE. `deserialize_graph()` hard-fails on a version mismatch
rather than silently migrating -- the same conservative policy M11-G9's
`gold_hash_freeze.json` check already uses for a different artifact.
"""

ALL_SEVENTEEN_TAGS: frozenset[str] = frozenset(a.tag for a in ALL_ALIASES)
"""The live, existing 17-tag set -- read directly off
`competency_aliases.ALL_ALIASES`, never hand-retyped, so this module can
never silently drift from production's own tag list."""


# ---------------------------------------------------------------------------
# Phase 2 -- node identity
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConceptRef:
    """A reference into EXACTLY ONE of the two existing, disjoint
    concept namespaces -- never a third, invented id shape.

    `registry_concept_id`: a real or `"unresolved:<term>"` id, validated
    via the EXISTING `concepts.registry.is_valid_concept_id()` -- the
    same validity rule `JobRequirement.concept_id` already enforces, not
    a second copy of it.

    `competency_tag`: a free, UNREGISTERED slug (one of the 17 existing
    tags, a v3 pilot tag, or a brand-new proposed concept) -- never
    validated against any registry, mirroring
    `NormalizedReference.competency_tag`'s own, deliberate policy.

    `.key` disambiguates the two namespaces explicitly (`"concept:..."`
    vs `"tag:..."`) so a tag slug can never be silently confused with a
    registry id as a graph node identity, even though their string
    shapes already differ in practice (dotted vs kebab-case) -- this
    makes the separation an enforced invariant, not an accident of
    naming convention.
    """

    registry_concept_id: str | None = None
    competency_tag: str | None = None

    def __post_init__(self) -> None:
        populated = [x is not None for x in (self.registry_concept_id, self.competency_tag)]
        if sum(populated) != 1:
            raise ValueError(
                "ConceptRef must set EXACTLY ONE of registry_concept_id/competency_tag, "
                f"got registry_concept_id={self.registry_concept_id!r} competency_tag={self.competency_tag!r}"
            )
        if self.registry_concept_id is not None and not is_valid_concept_id(self.registry_concept_id):
            raise ValueError(
                f"ConceptRef.registry_concept_id {self.registry_concept_id!r} is neither a "
                "registered TechnicalConcept id nor a valid 'unresolved:<term>' id"
            )
        if self.competency_tag is not None and not self.competency_tag.strip():
            raise ValueError("ConceptRef.competency_tag must not be empty/whitespace-only")

    @property
    def is_registry_concept(self) -> bool:
        return self.registry_concept_id is not None

    @property
    def key(self) -> str:
        if self.registry_concept_id is not None:
            return f"concept:{self.registry_concept_id}"
        return f"tag:{self.competency_tag}"


class ConceptStatus(str, Enum):
    """Where a concept node stands in this milestone's own review
    process -- INDEPENDENT of `GithubObservability` (a concept can be
    `REJECTED` and `STRONGLY_OBSERVABLE` at once, e.g. a real,
    observable technology that was still judged not worth promoting).

    `REJECTED` is a kept, visible node -- not a deletion -- specifically
    so a future proposal re-raising the same idea finds the prior
    decision recorded (M11-G9 Phase 2b's own "found but not promoted"
    list), rather than silently re-litigating it from scratch.
    """

    ACTIVE = "active"
    PROVISIONAL = "provisional"
    REJECTED = "rejected"


@dataclass(frozen=True)
class CompetencyConceptNode:
    """ONE concept identity -- deliberately carries NO claim-instance
    data (no source text, no source span, no necessity): those stay on
    `Qualification`/`JobRequirement`, which already own that dimension
    (Phase 6's explicit "what stays outside the graph" list).

    `tag_observability` is the ONE field with a non-obvious invariant:
    for a `registry_concept_id` node, observability is ALWAYS derived
    live from `observability.py`'s `TECHNICAL_DEFAULT_OBSERVABILITY`
    (see `effective_observability()`) -- storing a second, local copy
    here would create a second source of truth that can silently drift
    from the real policy, so `__post_init__` REJECTS a registry-concept
    node that tries to set one. For a `competency_tag` node there is no
    other source of truth at all, so `__post_init__` requires it be set
    explicitly -- never defaulted (Phase 3 invariant: "a concept's
    existence does not imply GitHub assessability").
    """

    ref: ConceptRef
    display_name: str
    status: ConceptStatus
    introduced_in: str
    tag_observability: GithubObservability | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.display_name.strip():
            raise ValueError("CompetencyConceptNode.display_name must not be empty/whitespace-only")
        if not self.introduced_in.strip():
            raise ValueError("CompetencyConceptNode.introduced_in must not be empty/whitespace-only")
        if self.ref.is_registry_concept and self.tag_observability is not None:
            raise ValueError(
                f"{self.ref.key}: a registry-concept node must never set tag_observability -- "
                "its observability is derived live from observability.py (effective_observability()), "
                "never duplicated here"
            )
        if not self.ref.is_registry_concept and self.tag_observability is None:
            raise ValueError(
                f"{self.ref.key}: a competency_tag node MUST set tag_observability explicitly -- "
                "there is no other source of truth for an unregistered tag's GitHub-assessability, "
                "and silently defaulting it would misrepresent what the concept's existence implies"
            )

    def effective_observability(self) -> GithubObservability:
        """The ONE place this module answers "is this concept the kind
        of thing GitHub evidence could ever speak to" -- dimension D
        from the mission's A/B/C/D/E separation. Never answers dimension
        E (whether evidence was actually FOUND for any real candidate)
        -- this module has no candidate, no repository, no evidence at
        all in scope."""
        if self.ref.is_registry_concept:
            return TECHNICAL_DEFAULT_OBSERVABILITY
        assert self.tag_observability is not None  # guaranteed by __post_init__
        return self.tag_observability


# ---------------------------------------------------------------------------
# Phase 2/3 -- typed relations and their safety semantics
# ---------------------------------------------------------------------------


class ConceptRelationType(str, Enum):
    """Every edge this graph can hold. Each member's docstring note
    names the Phase 3 safety invariant it exists to prevent violating.

    `EQUIVALENT` -- interchangeable for scoring purposes. Self-inverse.
      Safety: an EQUIVALENT edge must be explicitly authored per pair --
      never derived by chaining two other edges (no transitive closure,
      see `CompetencyConceptGraph.lookup_relation()`).

    `NARROWER_THAN` / `BROADER_THAN` -- a strict hierarchical pair,
      inverses of each other. Safety: representing that A is narrower
      than B is NEVER itself a claim that evidence for A satisfies a
      requirement for B -- this module provides no function that reads
      a `NARROWER_THAN` edge as a satisfaction rule at all.

    `RELATED_ONLY` -- associated, explicitly NOT equivalent and NOT
      hierarchical. Self-inverse. This is the Docker/Kubernetes,
      AWS/Azure relation -- see the reference graph below. Safety:
      `is_equivalent()` must return `False` for every `RELATED_ONLY`
      pair; no function anywhere in this module treats `RELATED_ONLY`
      as evidence-equivalent.

    `AMBIGUOUS` -- an explicit "two or more candidate concepts for the
      same raw phrase; do not auto-resolve" marker, distinct from
      `RELATED_ONLY`. Self-inverse. Safety:
      `CompetencyConceptGraph.lookup_relation()` returns a dedicated
      `status="ambiguous"` result for this case -- never silently
      picking one of the candidates.
    """

    EQUIVALENT = "equivalent"
    NARROWER_THAN = "narrower_than"
    BROADER_THAN = "broader_than"
    RELATED_ONLY = "related_only"
    AMBIGUOUS = "ambiguous"

    def inverse(self) -> "ConceptRelationType":
        return _INVERSE[self]


_INVERSE: dict[ConceptRelationType, ConceptRelationType] = {
    ConceptRelationType.EQUIVALENT: ConceptRelationType.EQUIVALENT,
    ConceptRelationType.NARROWER_THAN: ConceptRelationType.BROADER_THAN,
    ConceptRelationType.BROADER_THAN: ConceptRelationType.NARROWER_THAN,
    ConceptRelationType.RELATED_ONLY: ConceptRelationType.RELATED_ONLY,
    ConceptRelationType.AMBIGUOUS: ConceptRelationType.AMBIGUOUS,
}

_HIERARCHICAL_RELATIONS = frozenset({ConceptRelationType.NARROWER_THAN, ConceptRelationType.BROADER_THAN})


@dataclass(frozen=True)
class ConceptRelation:
    """One directed edge: `subject` RELATION `obj` (e.g. `docker
    RELATED_ONLY kubernetes`). Read `inverse()` off `relation`, not off
    a second stored edge -- storing both directions would risk the two
    copies silently disagreeing after an edit; this module stores each
    pair exactly once and derives the other direction on lookup.
    """

    subject: ConceptRef
    relation: ConceptRelationType
    obj: ConceptRef
    introduced_in: str
    note: str = ""

    def __post_init__(self) -> None:
        if self.subject.key == self.obj.key:
            raise ValueError(f"ConceptRelation cannot relate {self.subject.key!r} to itself")
        if not self.introduced_in.strip():
            raise ValueError("ConceptRelation.introduced_in must not be empty/whitespace-only")


@dataclass(frozen=True)
class RelationLookup:
    """The result of `lookup_relation()` -- THREE distinct statuses,
    never collapsed into a bool/None pair. `"unknown"` (Phase 3: "unknown
    relationships must fail conservatively") and `"ambiguous"` (Phase 3:
    "ambiguous aliases must not silently select an arbitrary concept")
    are kept apart from each other and from `"resolved"` specifically so
    a caller cannot mistake "we checked and found nothing" for "we found
    an explicit do-not-resolve marker."
    """

    status: str  # "resolved" | "unknown" | "ambiguous"
    relation: ConceptRelationType | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if self.status not in ("resolved", "unknown", "ambiguous"):
            raise ValueError(f"RelationLookup.status must be resolved/unknown/ambiguous, got {self.status!r}")
        if (self.status == "resolved") != (self.relation is not None):
            raise ValueError("RelationLookup.relation must be set iff status == 'resolved'")


# ---------------------------------------------------------------------------
# Phase 2/3/4 -- the graph itself
# ---------------------------------------------------------------------------


class CompetencyConceptGraph:
    """An immutable, in-memory node+edge index -- built once, validated
    at construction, never mutated afterward (mirrors
    `concepts.registry.ConceptRegistry`'s own "built once... never
    mutated" discipline).

    Construction rejects, by raising `ValueError`:
    - a duplicate node identity (two nodes with the same `.key`) --
      Phase 3 "identity collisions."
    - an edge referencing a node not present in `nodes` (no dangling
      edge).
    - a self-loop edge (`ConceptRelation.__post_init__` already blocks
      this, re-checked here for defense in depth).
    - two edges between the same unordered pair that disagree (a
      duplicate in the SAME direction, or an edge in the reverse
      direction whose relation is not exactly the stored edge's
      `inverse()`) -- Phase 3 "contradicting duplicate" rejection, so
      the graph can never hold two different answers for one pair.
    - a cycle in the HIERARCHICAL (`NARROWER_THAN`/`BROADER_THAN`) only
      sub-graph -- Phase 3 "cycles." `EQUIVALENT`/`RELATED_ONLY`/
      `AMBIGUOUS` edges are symmetric, non-hierarchical relations for
      which "cycle" is not a meaningful defect (a cluster of mutually
      `EQUIVALENT` synonyms is an intentional, valid shape), so they are
      excluded from this check by design, not by oversight.
    """

    def __init__(self, nodes: tuple[CompetencyConceptNode, ...], edges: tuple[ConceptRelation, ...]):
        self._nodes: dict[str, CompetencyConceptNode] = {}
        for node in nodes:
            if node.ref.key in self._nodes:
                raise ValueError(f"duplicate node identity: {node.ref.key!r}")
            self._nodes[node.ref.key] = node

        pair_relation: dict[tuple[str, str], ConceptRelationType] = {}
        for edge in edges:
            if edge.subject.key not in self._nodes:
                raise ValueError(f"edge references unknown node: {edge.subject.key!r}")
            if edge.obj.key not in self._nodes:
                raise ValueError(f"edge references unknown node: {edge.obj.key!r}")

            forward = (edge.subject.key, edge.obj.key)
            backward = (edge.obj.key, edge.subject.key)
            if forward in pair_relation:
                raise ValueError(f"duplicate edge between {forward!r}")
            if backward in pair_relation and pair_relation[backward] != edge.relation.inverse():
                raise ValueError(
                    f"contradicting edge: {forward!r} as {edge.relation.value!r} conflicts with the "
                    f"already-stored reverse-direction edge {pair_relation[backward].value!r}"
                )
            pair_relation[forward] = edge.relation

        self._edges: tuple[ConceptRelation, ...] = tuple(edges)
        self._check_acyclic_hierarchy()

    def _check_acyclic_hierarchy(self) -> None:
        """DFS cycle check restricted to the hierarchical sub-graph,
        normalized to one direction (narrower -> broader) so a
        `NARROWER_THAN` edge and an equivalent-meaning `BROADER_THAN`
        edge stored the other way are checked identically."""
        narrower_to_broader: dict[str, list[str]] = defaultdict(list)
        for edge in self._edges:
            if edge.relation == ConceptRelationType.NARROWER_THAN:
                narrower_to_broader[edge.subject.key].append(edge.obj.key)
            elif edge.relation == ConceptRelationType.BROADER_THAN:
                narrower_to_broader[edge.obj.key].append(edge.subject.key)

        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = defaultdict(int)

        def visit(node_key: str, path: list[str]) -> None:
            color[node_key] = GRAY
            for nxt in narrower_to_broader.get(node_key, ()):
                if color[nxt] == GRAY:
                    cycle = " -> ".join(path + [nxt])
                    raise ValueError(f"cycle in hierarchical (narrower/broader) relations: {cycle}")
                if color[nxt] == WHITE:
                    visit(nxt, path + [nxt])
            color[node_key] = BLACK

        for key in narrower_to_broader:
            if color[key] == WHITE:
                visit(key, [key])

    def node(self, ref: ConceptRef) -> CompetencyConceptNode | None:
        return self._nodes.get(ref.key)

    def all_nodes(self) -> tuple[CompetencyConceptNode, ...]:
        return tuple(self._nodes.values())

    def all_edges(self) -> tuple[ConceptRelation, ...]:
        return self._edges

    def lookup_relation(self, a: ConceptRef, b: ConceptRef) -> RelationLookup:
        """The ONE relation lookup this module provides. Deliberately
        returns only a DIRECT (one-hop, as-authored) relation -- NEVER a
        transitively-derived one, even for `EQUIVALENT`/`NARROWER_THAN`
        chains where transitivity would be mathematically valid (Phase 3:
        "no automatic transitive inference across related-concept
        edges," read conservatively here as applying to every relation
        type this module has, not only `RELATED_ONLY`). A future,
        explicitly separate utility could compute a transitive closure
        on request; this method never does so implicitly.
        """
        if a.key == b.key:
            raise ValueError("lookup_relation() called with the same concept on both sides")

        forward = [e.relation for e in self._edges if (e.subject.key, e.obj.key) == (a.key, b.key)]
        backward = [e.relation.inverse() for e in self._edges if (e.subject.key, e.obj.key) == (b.key, a.key)]
        candidates = forward + backward

        if not candidates:
            return RelationLookup(status="unknown")
        if any(c == ConceptRelationType.AMBIGUOUS for c in candidates):
            return RelationLookup(
                status="ambiguous",
                note="an AMBIGUOUS edge exists between these concepts -- do not auto-resolve",
            )
        # Construction already rejects a contradicting duplicate, so every
        # remaining candidate here is consistent; there can be at most one.
        return RelationLookup(status="resolved", relation=candidates[0])

    def is_equivalent(self, a: ConceptRef, b: ConceptRef) -> bool:
        """True only for a DIRECT, explicitly-authored `EQUIVALENT`
        edge. False for `RELATED_ONLY` (Phase 3: "related concepts are
        not equivalent"), false for an unknown pair, false for an
        ambiguous pair -- `is_equivalent()` never raises on an
        unresolved pair; it is a safe, total predicate precisely because
        "not known to be equivalent" and "equivalent" are the only two
        answers a caller can safely act on without first consulting
        `lookup_relation()` for the richer status.
        """
        result = self.lookup_relation(a, b)
        return result.status == "resolved" and result.relation == ConceptRelationType.EQUIVALENT

    # Deliberately NO `satisfies()` / `implies_support()` /
    # `transitive_closure()` method. The ABSENCE of such a method is
    # itself the Phase 3 safety invariant ("no automatic transitive
    # inference," "a narrower concept must not automatically prove a
    # broader qualification") -- verified structurally in
    # tests/test_m11g10_competency_concept_model.py rather than merely
    # asserted here.


# ---------------------------------------------------------------------------
# Phase 4 -- bounded, representative reference graph
#
# Every REAL (non-synthetic) node below maps to an EXISTING production
# tag/concept or an EXISTING M11-G9 finding -- no new ontology claim is
# invented for this fixture. Every edge is RELATED_ONLY: this fixture
# deliberately makes NO hierarchy/equivalence claim about real production
# concepts (those would be genuine ontology decisions this bounded
# milestone is not authorized to make). Hierarchy/equivalence/ambiguity/
# cycle MECHANISM tests instead use clearly-labelled synthetic throwaway
# nodes, built inline in the test file -- never mixed into this fixture.
# ---------------------------------------------------------------------------


def _tag_node(tag: str, status: ConceptStatus, introduced_in: str, observability: GithubObservability, notes: str = "") -> CompetencyConceptNode:
    return CompetencyConceptNode(
        ref=ConceptRef(competency_tag=tag),
        display_name=tag.replace("-", " ").title(),
        status=status,
        introduced_in=introduced_in,
        tag_observability=observability,
        notes=notes,
    )


def _concept_node(concept_id: str, display_name: str, introduced_in: str, notes: str = "") -> CompetencyConceptNode:
    return CompetencyConceptNode(
        ref=ConceptRef(registry_concept_id=concept_id),
        display_name=display_name,
        status=ConceptStatus.ACTIVE,
        introduced_in=introduced_in,
        notes=notes,
    )


_V3_NEW_CONCEPT_OBSERVABILITY: dict[str, GithubObservability] = {
    "generative-ai-agentic-systems": GithubObservability.PARTIALLY_OBSERVABLE,
    "cloud-infrastructure-devops": GithubObservability.STRONGLY_OBSERVABLE,
    "data-engineering-pipelines": GithubObservability.STRONGLY_OBSERVABLE,
}
"""Mirrors `m11g9_competency_extraction_v3._V3_NEW_CONCEPT_OBSERVABILITY`
exactly (hand-copied, not imported, to avoid this module depending on
v3's private module-level name reaching across two evaluation-only
scripts -- the VALUES are pinned identical by
`tests/test_m11g10_competency_concept_model.py`'s own cross-check
against the real v3 module, so a future drift is caught, not silently
inherited)."""

_REJECTED_G9_CONCEPTS: dict[str, GithubObservability] = {
    # M11-G9 Phase 2b: proposed, found in the G9 corpus, NOT promoted
    # (recurrence bar not met within that single 14-posting corpus).
    # Observability judged per G9's own §2d finding that these are
    # directly, strongly observable from repository content when
    # represented at all -- kept REJECTED here, not re-litigated.
    "identity-authorization-oauth-oidc": GithubObservability.STRONGLY_OBSERVABLE,
    "robotics-middleware-ros": GithubObservability.PARTIALLY_OBSERVABLE,
}


def build_reference_graph() -> CompetencyConceptGraph:
    """The Phase 4 bounded, representative graph: all 17 existing
    production tags (status ACTIVE, observability read live off
    `competency_extraction._COMPETENCY_OBSERVABILITY` -- never
    hand-retyped), v3's 3 pilot concepts (status PROVISIONAL -- "not
    automatically approved production ontology entries," per this
    milestone's own instruction), 2 representative M11-G9 REJECTED
    concepts, 3 real registry `TechnicalConcept`s (Docker, Kubernetes,
    AWS), and 1 illustrative PROVISIONAL pilot node standing in for
    "Azure" (not a registered `TechnicalConcept` today -- introduced
    here ONLY to exercise the AWS/Azure adversarial safety test named
    explicitly in this milestone's brief, clearly marked as such, never
    presented as an approved registry proposal).
    """
    nodes: list[CompetencyConceptNode] = []

    for tag in sorted(ALL_SEVENTEEN_TAGS):
        nodes.append(_tag_node(tag, ConceptStatus.ACTIVE, "M11-C", _COMPETENCY_OBSERVABILITY[tag]))

    for tag, obs in _V3_NEW_CONCEPT_OBSERVABILITY.items():
        nodes.append(_tag_node(tag, ConceptStatus.PROVISIONAL, "M11-G9", obs, notes="v3 pilot concept, not yet production-approved"))

    for tag, obs in _REJECTED_G9_CONCEPTS.items():
        nodes.append(_tag_node(tag, ConceptStatus.REJECTED, "M11-G9", obs, notes="proposed in M11-G9 Phase 2b, not promoted (recurrence bar not met)"))

    nodes.append(_concept_node("infra.docker", "Docker", "M11-5C"))
    nodes.append(_concept_node("infra.kubernetes", "Kubernetes", "M11-8D.1"))
    nodes.append(_concept_node("cloud.aws", "AWS", "M11-5C"))

    nodes.append(_tag_node(
        "cloud-platform-azure-pilot", ConceptStatus.PROVISIONAL, "M11-G10",
        GithubObservability.STRONGLY_OBSERVABLE,
        notes="illustrative pilot node for this milestone's AWS/Azure adversarial safety test ONLY -- "
              "Azure is not a registered TechnicalConcept today; this is NOT a reviewed ontology proposal",
    ))

    edges = (
        ConceptRelation(
            ConceptRef(registry_concept_id="infra.docker"), ConceptRelationType.RELATED_ONLY,
            ConceptRef(registry_concept_id="infra.kubernetes"), "M11-G10",
            note="both containerization/orchestration technologies; operationally associated, never equivalent "
                 "(Phase 3 adversarial fixture: 'Docker must not automatically prove Kubernetes')",
        ),
        ConceptRelation(
            ConceptRef(registry_concept_id="cloud.aws"), ConceptRelationType.RELATED_ONLY,
            ConceptRef(competency_tag="cloud-platform-azure-pilot"), "M11-G10",
            note="both cloud platforms; never equivalent (Phase 3 adversarial fixture: "
                 "'AWS must not automatically prove Azure')",
        ),
        ConceptRelation(
            ConceptRef(competency_tag="generative-ai-agentic-systems"), ConceptRelationType.RELATED_ONLY,
            ConceptRef(competency_tag="ml-fundamentals"), "M11-G10",
            note="grounded in M11-G9 doc section 2c.3: operating/using generative-AI tooling is not the "
                 "same competency as understanding ML theory",
        ),
        ConceptRelation(
            ConceptRef(competency_tag="data-engineering-pipelines"), ConceptRelationType.RELATED_ONLY,
            ConceptRef(competency_tag="database-design"), "M11-G10",
            note="grounded in M11-G9 doc section 2e: data-engineering/ETL sits between database-design and "
                 "distributed-systems without being narrower than either -- RELATED_ONLY, not NARROWER_THAN",
        ),
        ConceptRelation(
            ConceptRef(competency_tag="cloud-infrastructure-devops"), ConceptRelationType.RELATED_ONLY,
            ConceptRef(registry_concept_id="infra.docker"), "M11-G10",
            note="DevOps/IaC practice is related to, but not equivalent to, using Docker specifically",
        ),
        ConceptRelation(
            ConceptRef(competency_tag="identity-authorization-oauth-oidc"), ConceptRelationType.RELATED_ONLY,
            ConceptRef(competency_tag="cybersecurity-threat-modeling"), "M11-G10",
            note="identity/authorization and security-threat-modeling are adjacent security disciplines, "
                 "never equivalent (mirrors M11-G9 doc section 2c.1's own 'adjacent discipline, not the same "
                 "competency' finding for a different pair)",
        ),
    )

    return CompetencyConceptGraph(tuple(nodes), edges)


# ---------------------------------------------------------------------------
# Phase 5 -- legacy compatibility adapter (NormalizedReference <-> ConceptRef)
# ---------------------------------------------------------------------------


def concept_ref_from_normalized_reference(ref: NormalizedReference) -> ConceptRef | None:
    """Adapts an EXISTING `NormalizedReference` (Milestone 11-B,
    production-shaped but not production-wired) into this module's
    `ConceptRef`, for exactly the two single-concept shapes this small
    model supports.

    Returns `None` -- an EXPLICIT decline, never a guess -- for a
    `NormalizedReference` carrying a populated `alternative_concept_ids`
    GROUP: this milestone's minimal model has no multi-concept node
    shape (Phase 5 "explicitly decline unsupported legacy projections").
    A future migration that needs to represent an alternative group in
    this graph would be a genuine, separate extension, not an implicit
    silent one.
    """
    if ref.alternative_concept_ids:
        return None
    if ref.concept_id is not None:
        return ConceptRef(registry_concept_id=ref.concept_id)
    if ref.competency_tag is not None:
        return ConceptRef(competency_tag=ref.competency_tag)
    return None  # NormalizedReference with neither field set (the "illustrative, non-exhaustive" case)


def normalized_reference_from_concept_ref(ref: ConceptRef) -> NormalizedReference:
    """The reverse direction -- always succeeds, since every `ConceptRef`
    is one of the two shapes `NormalizedReference` already supports."""
    if ref.is_registry_concept:
        return NormalizedReference(concept_id=ref.registry_concept_id)
    return NormalizedReference(competency_tag=ref.competency_tag)


# ---------------------------------------------------------------------------
# Phase 4 -- deterministic serialization
# ---------------------------------------------------------------------------


def serialize_graph(graph: CompetencyConceptGraph) -> dict:
    """A plain, deterministic dict -- stable key order via explicit
    construction, never relying on dict-ordering-by-insertion-accident.
    Suitable for `json.dumps(..., sort_keys=True)`."""
    return {
        "model_version": COMPETENCY_CONCEPT_MODEL_VERSION,
        "nodes": [
            {
                "registry_concept_id": node.ref.registry_concept_id,
                "competency_tag": node.ref.competency_tag,
                "display_name": node.display_name,
                "status": node.status.value,
                "introduced_in": node.introduced_in,
                "tag_observability": node.tag_observability.name if node.tag_observability is not None else None,
                "notes": node.notes,
            }
            for node in sorted(graph.all_nodes(), key=lambda n: n.ref.key)
        ],
        "edges": [
            {
                "subject": edge.subject.key,
                "relation": edge.relation.value,
                "object": edge.obj.key,
                "introduced_in": edge.introduced_in,
                "note": edge.note,
            }
            for edge in sorted(graph.all_edges(), key=lambda e: (e.subject.key, e.relation.value, e.obj.key))
        ],
    }


def deserialize_graph(data: dict) -> CompetencyConceptGraph:
    """Hard-fails (raises `ValueError`) on a `model_version` mismatch --
    never silently migrates, mirroring M11-G9's own
    `gold_hash_freeze.json` hard-failure policy for a different
    artifact (Phase 3 'schema-version compatibility')."""
    if data.get("model_version") != COMPETENCY_CONCEPT_MODEL_VERSION:
        raise ValueError(
            f"model_version mismatch: graph data is version {data.get('model_version')!r}, "
            f"this module is version {COMPETENCY_CONCEPT_MODEL_VERSION!r} -- refusing to silently migrate"
        )
    nodes = tuple(
        CompetencyConceptNode(
            ref=ConceptRef(
                registry_concept_id=row["registry_concept_id"],
                competency_tag=row["competency_tag"],
            ),
            display_name=row["display_name"],
            status=ConceptStatus(row["status"]),
            introduced_in=row["introduced_in"],
            tag_observability=GithubObservability[row["tag_observability"]] if row["tag_observability"] else None,
            notes=row["notes"],
        )
        for row in data["nodes"]
    )
    by_key = {n.ref.key: n.ref for n in nodes}
    edges = tuple(
        ConceptRelation(
            subject=by_key[row["subject"]],
            relation=ConceptRelationType(row["relation"]),
            obj=by_key[row["object"]],
            introduced_in=row["introduced_in"],
            note=row["note"],
        )
        for row in data["edges"]
    )
    return CompetencyConceptGraph(nodes, edges)
