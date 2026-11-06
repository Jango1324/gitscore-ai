"""Milestone 11-G10 -- minimal CompetencyConcept data model: safety
invariants, legacy compatibility, and no-production-integration checks.

Evaluation-only, exactly like `test_m11g9_v3_feasibility.py` before it --
imports only the new offline module plus plain, read-only production
types; constructs no live pipeline state.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "evaluation_lib"))

import m11g10_competency_concept_model as m  # noqa: E402
from gitscore.jobs.parsing.qualification import NormalizedReference  # noqa: E402
from gitscore.jobs.types import GithubObservability  # noqa: E402


# ---------------------------------------------------------------------------
# Phase 7 -- no production integration
# ---------------------------------------------------------------------------


def test_module_does_not_live_under_src_gitscore():
    import importlib
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("gitscore.jobs.parsing.competency_concept_model")


def test_module_is_not_imported_by_production():
    src_root = REPO_ROOT / "src" / "gitscore"
    offenders = []
    for path in src_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "m11g10" in text.lower() or "competency_concept_model" in text:
            offenders.append(str(path))
    assert offenders == [], f"the G10 model must never be referenced from src/gitscore: {offenders}"


def test_matcher_and_registry_modules_unchanged_by_import():
    """Importing this module must not mutate `concepts.registry` or
    `matching.support`/`matching.engine` state -- it only reads from
    them."""
    import gitscore.concepts.registry as registry
    import gitscore.matching.support as support

    before_registry = registry.default_registry().all_concepts()
    before_min_confidence = support.MINIMUM_SUPPORTING_CONFIDENCE

    m.build_reference_graph()  # construct a graph; must not mutate anything

    assert registry.default_registry().all_concepts() == before_registry
    assert support.MINIMUM_SUPPORTING_CONFIDENCE == before_min_confidence


def test_module_never_imports_necessity_evidence_or_scoring_types():
    """Structural proof that job necessity, repository evidence, and
    candidate-evaluation/scoring are outside this graph's vocabulary
    entirely (Phase 6's explicit 'what stays outside the graph' list)."""
    source = Path(m.__file__).read_text(encoding="utf-8")
    forbidden = ["Necessity", "CandidateEvidenceProfile", "CandidateConceptSummary", "match_job", "match_requirement", "ScoreBreakdown"]
    offenders = [name for name in forbidden if name in source]
    assert offenders == [], f"G10 model must not reference job-necessity/evidence/scoring types: {offenders}"


def test_module_provides_no_transitive_or_satisfaction_inference_function():
    """The ABSENCE of a satisfies()/implies_support()/transitive_closure()
    style function IS the safety invariant -- checked by enumerating every
    public callable the module actually exposes."""
    public_callables = [name for name in dir(m) if not name.startswith("_") and callable(getattr(m, name))]
    forbidden_fragments = ["satisf", "entail", "implie", "transitive", "closure", "support"]
    offenders = [
        name for name in public_callables
        if any(frag in name.lower() for frag in forbidden_fragments)
    ]
    assert offenders == [], f"module must expose no satisfaction/transitive-inference function: {offenders}"


# ---------------------------------------------------------------------------
# Phase 3 -- safety invariants on the REAL reference graph
# ---------------------------------------------------------------------------


def test_docker_does_not_prove_kubernetes():
    g = m.build_reference_graph()
    docker = m.ConceptRef(registry_concept_id="infra.docker")
    k8s = m.ConceptRef(registry_concept_id="infra.kubernetes")
    result = g.lookup_relation(docker, k8s)
    assert result.status == "resolved"
    assert result.relation == m.ConceptRelationType.RELATED_ONLY
    assert g.is_equivalent(docker, k8s) is False


def test_aws_does_not_prove_azure():
    g = m.build_reference_graph()
    aws = m.ConceptRef(registry_concept_id="cloud.aws")
    azure = m.ConceptRef(competency_tag="cloud-platform-azure-pilot")
    result = g.lookup_relation(aws, azure)
    assert result.status == "resolved"
    assert result.relation == m.ConceptRelationType.RELATED_ONLY
    assert g.is_equivalent(aws, azure) is False


def test_related_only_is_never_equivalent_for_every_edge_in_reference_graph():
    g = m.build_reference_graph()
    for edge in g.all_edges():
        if edge.relation == m.ConceptRelationType.RELATED_ONLY:
            assert g.is_equivalent(edge.subject, edge.obj) is False
            assert g.is_equivalent(edge.obj, edge.subject) is False


def test_unknown_pair_fails_conservatively_not_as_related_or_equivalent():
    g = m.build_reference_graph()
    a = m.ConceptRef(competency_tag="circuit-theory")
    b = m.ConceptRef(competency_tag="quantum-computing")  # no edge authored between these
    result = g.lookup_relation(a, b)
    assert result.status == "unknown"
    assert result.relation is None
    assert g.is_equivalent(a, b) is False


def test_ambiguous_relation_is_not_silently_resolved():
    """Synthetic throwaway graph -- never mixed into the real reference
    fixture -- purely to exercise the AMBIGUOUS mechanism."""
    a = m.CompetencyConceptNode(m.ConceptRef(competency_tag="_synthetic_demo_a"), "Synthetic A", m.ConceptStatus.PROVISIONAL, "M11-G10-test", tag_observability=GithubObservability.PARTIALLY_OBSERVABLE)
    b = m.CompetencyConceptNode(m.ConceptRef(competency_tag="_synthetic_demo_b"), "Synthetic B", m.ConceptStatus.PROVISIONAL, "M11-G10-test", tag_observability=GithubObservability.PARTIALLY_OBSERVABLE)
    c = m.CompetencyConceptNode(m.ConceptRef(competency_tag="_synthetic_demo_c"), "Synthetic C", m.ConceptStatus.PROVISIONAL, "M11-G10-test", tag_observability=GithubObservability.PARTIALLY_OBSERVABLE)
    edge = m.ConceptRelation(a.ref, m.ConceptRelationType.AMBIGUOUS, b.ref, "M11-G10-test")
    g = m.CompetencyConceptGraph((a, b, c), (edge,))

    result = g.lookup_relation(a.ref, b.ref)
    assert result.status == "ambiguous"
    assert result.relation is None
    assert g.is_equivalent(a.ref, b.ref) is False
    # and the untouched third node remains plainly unknown, not swept into ambiguity
    assert g.lookup_relation(a.ref, c.ref).status == "unknown"


def test_no_transitive_inference_across_narrower_chain():
    """A narrower_than B, B narrower_than C -- querying A vs C directly
    must be 'unknown,' never a derived transitive relation."""
    a = m.CompetencyConceptNode(m.ConceptRef(competency_tag="_synthetic_chain_a"), "A", m.ConceptStatus.PROVISIONAL, "M11-G10-test", tag_observability=GithubObservability.PARTIALLY_OBSERVABLE)
    b = m.CompetencyConceptNode(m.ConceptRef(competency_tag="_synthetic_chain_b"), "B", m.ConceptStatus.PROVISIONAL, "M11-G10-test", tag_observability=GithubObservability.PARTIALLY_OBSERVABLE)
    c = m.CompetencyConceptNode(m.ConceptRef(competency_tag="_synthetic_chain_c"), "C", m.ConceptStatus.PROVISIONAL, "M11-G10-test", tag_observability=GithubObservability.PARTIALLY_OBSERVABLE)
    edges = (
        m.ConceptRelation(a.ref, m.ConceptRelationType.NARROWER_THAN, b.ref, "M11-G10-test"),
        m.ConceptRelation(b.ref, m.ConceptRelationType.NARROWER_THAN, c.ref, "M11-G10-test"),
    )
    g = m.CompetencyConceptGraph((a, b, c), edges)

    assert g.lookup_relation(a.ref, b.ref).relation == m.ConceptRelationType.NARROWER_THAN
    assert g.lookup_relation(b.ref, c.ref).relation == m.ConceptRelationType.NARROWER_THAN
    direct_a_c = g.lookup_relation(a.ref, c.ref)
    assert direct_a_c.status == "unknown", "A/C must stay unknown -- no transitive NARROWER_THAN is derived"


def test_narrower_than_and_broader_than_are_exact_inverses():
    assert m.ConceptRelationType.NARROWER_THAN.inverse() == m.ConceptRelationType.BROADER_THAN
    assert m.ConceptRelationType.BROADER_THAN.inverse() == m.ConceptRelationType.NARROWER_THAN
    for self_inverse in (m.ConceptRelationType.EQUIVALENT, m.ConceptRelationType.RELATED_ONLY, m.ConceptRelationType.AMBIGUOUS):
        assert self_inverse.inverse() == self_inverse


def test_hierarchy_cycle_is_rejected_at_construction():
    a = m.CompetencyConceptNode(m.ConceptRef(competency_tag="_synthetic_cycle_a"), "A", m.ConceptStatus.PROVISIONAL, "M11-G10-test", tag_observability=GithubObservability.PARTIALLY_OBSERVABLE)
    b = m.CompetencyConceptNode(m.ConceptRef(competency_tag="_synthetic_cycle_b"), "B", m.ConceptStatus.PROVISIONAL, "M11-G10-test", tag_observability=GithubObservability.PARTIALLY_OBSERVABLE)
    c = m.CompetencyConceptNode(m.ConceptRef(competency_tag="_synthetic_cycle_c"), "C", m.ConceptStatus.PROVISIONAL, "M11-G10-test", tag_observability=GithubObservability.PARTIALLY_OBSERVABLE)
    edges = (
        m.ConceptRelation(a.ref, m.ConceptRelationType.NARROWER_THAN, b.ref, "M11-G10-test"),
        m.ConceptRelation(b.ref, m.ConceptRelationType.NARROWER_THAN, c.ref, "M11-G10-test"),
        m.ConceptRelation(c.ref, m.ConceptRelationType.NARROWER_THAN, a.ref, "M11-G10-test"),
    )
    with pytest.raises(ValueError, match="cycle"):
        m.CompetencyConceptGraph((a, b, c), edges)


def test_equivalent_cluster_cycle_is_allowed():
    """A mutually-EQUIVALENT cluster forming a cycle is explicitly fine
    -- EQUIVALENT/RELATED_ONLY/AMBIGUOUS are symmetric, non-hierarchical
    relations for which 'cycle' is not a defect."""
    a = m.CompetencyConceptNode(m.ConceptRef(competency_tag="_synthetic_equiv_a"), "A", m.ConceptStatus.PROVISIONAL, "M11-G10-test", tag_observability=GithubObservability.PARTIALLY_OBSERVABLE)
    b = m.CompetencyConceptNode(m.ConceptRef(competency_tag="_synthetic_equiv_b"), "B", m.ConceptStatus.PROVISIONAL, "M11-G10-test", tag_observability=GithubObservability.PARTIALLY_OBSERVABLE)
    edges = (m.ConceptRelation(a.ref, m.ConceptRelationType.EQUIVALENT, b.ref, "M11-G10-test"),)
    g = m.CompetencyConceptGraph((a, b), edges)  # must not raise
    assert g.is_equivalent(a.ref, b.ref) is True
    assert g.is_equivalent(b.ref, a.ref) is True  # symmetric via inverse lookup


def test_duplicate_node_identity_is_rejected():
    a = m.CompetencyConceptNode(m.ConceptRef(competency_tag="_synthetic_dup"), "A", m.ConceptStatus.PROVISIONAL, "M11-G10-test", tag_observability=GithubObservability.PARTIALLY_OBSERVABLE)
    a2 = m.CompetencyConceptNode(m.ConceptRef(competency_tag="_synthetic_dup"), "A again", m.ConceptStatus.PROVISIONAL, "M11-G10-test", tag_observability=GithubObservability.PARTIALLY_OBSERVABLE)
    with pytest.raises(ValueError, match="duplicate node identity"):
        m.CompetencyConceptGraph((a, a2), ())


def test_dangling_edge_is_rejected():
    a = m.CompetencyConceptNode(m.ConceptRef(competency_tag="_synthetic_dangle_a"), "A", m.ConceptStatus.PROVISIONAL, "M11-G10-test", tag_observability=GithubObservability.PARTIALLY_OBSERVABLE)
    missing_ref = m.ConceptRef(competency_tag="_synthetic_dangle_missing")
    edge = m.ConceptRelation(a.ref, m.ConceptRelationType.RELATED_ONLY, missing_ref, "M11-G10-test")
    with pytest.raises(ValueError, match="unknown node"):
        m.CompetencyConceptGraph((a,), (edge,))


def test_contradicting_reverse_edge_is_rejected():
    a = m.CompetencyConceptNode(m.ConceptRef(competency_tag="_synthetic_contra_a"), "A", m.ConceptStatus.PROVISIONAL, "M11-G10-test", tag_observability=GithubObservability.PARTIALLY_OBSERVABLE)
    b = m.CompetencyConceptNode(m.ConceptRef(competency_tag="_synthetic_contra_b"), "B", m.ConceptStatus.PROVISIONAL, "M11-G10-test", tag_observability=GithubObservability.PARTIALLY_OBSERVABLE)
    edges = (
        m.ConceptRelation(a.ref, m.ConceptRelationType.NARROWER_THAN, b.ref, "M11-G10-test"),
        # B -> A as NARROWER_THAN contradicts A NARROWER_THAN B (should be BROADER_THAN to agree)
        m.ConceptRelation(b.ref, m.ConceptRelationType.NARROWER_THAN, a.ref, "M11-G10-test"),
    )
    with pytest.raises(ValueError, match="contradicting edge"):
        m.CompetencyConceptGraph((a, b), edges)


def test_self_loop_edge_is_rejected():
    a = m.CompetencyConceptNode(m.ConceptRef(competency_tag="_synthetic_self"), "A", m.ConceptStatus.PROVISIONAL, "M11-G10-test", tag_observability=GithubObservability.PARTIALLY_OBSERVABLE)
    with pytest.raises(ValueError, match="cannot relate"):
        m.ConceptRelation(a.ref, m.ConceptRelationType.RELATED_ONLY, a.ref, "M11-G10-test")


def test_concept_ref_rejects_both_or_neither_field_populated():
    with pytest.raises(ValueError):
        m.ConceptRef()
    with pytest.raises(ValueError):
        m.ConceptRef(registry_concept_id="infra.docker", competency_tag="distributed-systems")


def test_concept_ref_rejects_invalid_registry_id():
    with pytest.raises(ValueError):
        m.ConceptRef(registry_concept_id="not.a.real.concept.id.and.not.unresolved.shaped ")


def test_tag_node_must_declare_observability_explicitly():
    with pytest.raises(ValueError, match="MUST set tag_observability"):
        m.CompetencyConceptNode(m.ConceptRef(competency_tag="_synthetic_no_obs"), "A", m.ConceptStatus.PROVISIONAL, "M11-G10-test")


def test_registry_concept_node_must_not_set_local_observability():
    with pytest.raises(ValueError, match="must never set tag_observability"):
        m.CompetencyConceptNode(
            m.ConceptRef(registry_concept_id="infra.docker"), "Docker", m.ConceptStatus.ACTIVE, "M11-5C",
            tag_observability=GithubObservability.STRONGLY_OBSERVABLE,
        )


def test_registry_concept_observability_is_derived_live_not_duplicated():
    from gitscore.jobs.parsing.observability import TECHNICAL_DEFAULT_OBSERVABILITY
    node = m.CompetencyConceptNode(m.ConceptRef(registry_concept_id="infra.docker"), "Docker", m.ConceptStatus.ACTIVE, "M11-5C")
    assert node.effective_observability() == TECHNICAL_DEFAULT_OBSERVABILITY


# ---------------------------------------------------------------------------
# Phase 5 -- legacy compatibility
# ---------------------------------------------------------------------------


def test_round_trips_a_registered_concept_normalized_reference():
    original = NormalizedReference(concept_id="infra.docker")
    ref = m.concept_ref_from_normalized_reference(original)
    assert ref == m.ConceptRef(registry_concept_id="infra.docker")
    restored = m.normalized_reference_from_concept_ref(ref)
    assert restored == original


def test_round_trips_a_competency_tag_normalized_reference():
    original = NormalizedReference(competency_tag="distributed-systems")
    ref = m.concept_ref_from_normalized_reference(original)
    assert ref == m.ConceptRef(competency_tag="distributed-systems")
    restored = m.normalized_reference_from_concept_ref(ref)
    assert restored == original


def test_alternative_concept_group_is_explicitly_declined_not_guessed():
    group_ref = NormalizedReference(alternative_concept_ids=("language.python", "language.go"))
    assert m.concept_ref_from_normalized_reference(group_ref) is None


def test_illustrative_empty_normalized_reference_is_declined():
    empty_ref = NormalizedReference(exhaustive=False)
    assert m.concept_ref_from_normalized_reference(empty_ref) is None


def test_every_existing_17_tag_is_present_in_reference_graph_as_active():
    g = m.build_reference_graph()
    for tag in m.ALL_SEVENTEEN_TAGS:
        node = g.node(m.ConceptRef(competency_tag=tag))
        assert node is not None, f"existing tag {tag!r} missing from reference graph"
        assert node.status == m.ConceptStatus.ACTIVE


def test_v3_pilot_concepts_present_as_provisional_not_active():
    g = m.build_reference_graph()
    for tag in ("generative-ai-agentic-systems", "cloud-infrastructure-devops", "data-engineering-pipelines"):
        node = g.node(m.ConceptRef(competency_tag=tag))
        assert node is not None
        assert node.status == m.ConceptStatus.PROVISIONAL, f"{tag} must be PROVISIONAL, not auto-approved ACTIVE"


def test_v3_pilot_concept_keys_are_disjoint_from_existing_17_tags():
    overlap = set(m._V3_NEW_CONCEPT_OBSERVABILITY) & m.ALL_SEVENTEEN_TAGS
    assert overlap == set()


def test_v3_pilot_observability_values_match_the_real_v3_module():
    """This module hand-mirrors v3's observability table (see its own
    docstring for why) -- pinned here so a future edit to EITHER table
    that drifts from the other is caught, not silently inherited."""
    v3 = pytest.importorskip("m11g9_competency_extraction_v3")
    assert m._V3_NEW_CONCEPT_OBSERVABILITY == v3._V3_NEW_CONCEPT_OBSERVABILITY


def test_no_new_relationship_changes_matching_engine_output():
    """Building and querying this graph must not change what the EXISTING
    matcher produces for a fixed, already-existing manual example."""
    from gitscore.jobs.models import JobRequirement
    from gitscore.jobs.types import GithubObservability as GO
    from gitscore.jobs.types import Importance, Necessity
    from gitscore.evidence.profile import build_candidate_evidence_profile
    from gitscore.matching.engine import match_requirement

    requirement = JobRequirement(
        original_text="Docker experience required.",
        necessity=Necessity.REQUIRED,
        importance=Importance.HIGH,
        github_observability=GO.STRONGLY_OBSERVABLE,
        concept_id="infra.docker",
    )
    empty_profile = build_candidate_evidence_profile("test-candidate", discovered=(), analyzed=(), evidence_items=())

    before = match_requirement(requirement, empty_profile)
    m.build_reference_graph()  # exercise the new module in between
    after = match_requirement(requirement, empty_profile)

    assert before == after


# ---------------------------------------------------------------------------
# Phase 4 -- deterministic serialization / versioning
# ---------------------------------------------------------------------------


def test_serialization_round_trips_the_reference_graph():
    g = m.build_reference_graph()
    data = m.serialize_graph(g)
    g2 = m.deserialize_graph(data)
    assert {n.ref.key for n in g2.all_nodes()} == {n.ref.key for n in g.all_nodes()}
    assert len(g2.all_edges()) == len(g.all_edges())
    for edge in g.all_edges():
        assert g2.lookup_relation(edge.subject, edge.obj).relation == edge.relation


def test_serialization_is_deterministic_across_calls():
    g = m.build_reference_graph()
    assert m.serialize_graph(g) == m.serialize_graph(g)


def test_deserialize_rejects_version_mismatch():
    g = m.build_reference_graph()
    data = m.serialize_graph(g)
    data["model_version"] = 999
    with pytest.raises(ValueError, match="model_version mismatch"):
        m.deserialize_graph(data)
