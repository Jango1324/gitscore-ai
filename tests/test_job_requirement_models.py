"""Milestone 6A: gitscore.jobs (SourceSpan, JobRequirement)."""
import dataclasses

import pytest

from gitscore.concepts.registry import resolve_concept
from gitscore.jobs import GithubObservability, Importance, JobRequirement, Necessity, ParserConfidence, SourceSpan


def make_requirement(**overrides):
    base = dict(
        original_text="Experience with PostgreSQL",
        necessity=Necessity.REQUIRED,
        importance=Importance.HIGH,
        github_observability=GithubObservability.STRONGLY_OBSERVABLE,
        concept_id="database.postgresql",
    )
    base.update(overrides)
    return JobRequirement(**base)


# ---------------------------------------------------------------------------
# Technical, concept-resolved requirement
# ---------------------------------------------------------------------------

def test_technical_requirement_resolves_through_the_existing_concept_registry():
    resolution = resolve_concept("Postgres")
    assert resolution.matched
    requirement = make_requirement(concept_id=resolution.concept_id)

    assert requirement.concept_id == "database.postgresql"
    assert requirement.is_technical
    assert requirement.is_resolved_concept
    assert not requirement.is_unresolved_concept


def test_pytorch_alias_resolves_to_the_existing_concept():
    resolution = resolve_concept("PyTorch")
    requirement = make_requirement(
        original_text="Experience with PyTorch", concept_id=resolution.concept_id
    )
    assert requirement.concept_id == "ml.framework.pytorch"
    assert requirement.is_resolved_concept


# ---------------------------------------------------------------------------
# Technical, unresolved concept -- retained, never dropped, no registry mutation
# ---------------------------------------------------------------------------

def test_unresolved_technology_is_retained_not_dropped():
    resolution = resolve_concept("warp-level primitives")
    assert not resolution.matched
    requirement = make_requirement(
        original_text="Experience with warp-level primitives",
        concept_id=resolution.concept_id,
    )

    assert requirement.concept_id == "unresolved:warp-level_primitives"
    assert requirement.is_technical
    assert requirement.is_unresolved_concept
    assert not requirement.is_resolved_concept
    # The original raw term survives independently of concept resolution.
    assert requirement.original_text == "Experience with warp-level primitives"


def test_resolving_an_unknown_requirement_term_does_not_mutate_the_shared_registry():
    from gitscore.concepts.registry import default_registry

    registry = default_registry()
    before = len(registry.all_concepts())
    resolve_concept("some-unanticipated-tech-xyz")
    assert len(registry.all_concepts()) == before


# ---------------------------------------------------------------------------
# Non-technical / non-concept requirement (Part 6)
# ---------------------------------------------------------------------------

def test_non_technical_requirement_has_no_concept_id():
    requirement = make_requirement(
        original_text="3+ years of professional experience",
        concept_id=None,
        category="experience",
        github_observability=GithubObservability.NOT_OBSERVABLE,
    )
    assert requirement.concept_id is None
    assert not requirement.is_technical
    assert not requirement.is_resolved_concept
    assert not requirement.is_unresolved_concept
    assert requirement.original_text == "3+ years of professional experience"


def test_compound_sentence_splits_into_two_separate_requirement_claims():
    # "3+ years of experience building Python backend services" must NOT
    # collapse into one JobRequirement asserting both a GitHub-observable
    # concept AND a non-observable experience claim (Milestone 6A Part 1).
    sentence = "3+ years of experience building Python backend services"
    technical = make_requirement(
        original_text=sentence,
        concept_id=resolve_concept("Python").concept_id,
        github_observability=GithubObservability.STRONGLY_OBSERVABLE,
        category="language",
    )
    non_technical = make_requirement(
        original_text=sentence,
        concept_id=None,
        github_observability=GithubObservability.NOT_OBSERVABLE,
        category="experience",
    )
    assert technical.concept_id == "language.python"
    assert technical.github_observability == GithubObservability.STRONGLY_OBSERVABLE
    assert non_technical.concept_id is None
    assert non_technical.github_observability == GithubObservability.NOT_OBSERVABLE
    # Distinct claims -- not merged into a single object or silently deduped.
    assert technical != non_technical


# ---------------------------------------------------------------------------
# Necessity
# ---------------------------------------------------------------------------

def test_required_necessity():
    requirement = make_requirement(necessity=Necessity.REQUIRED)
    assert requirement.necessity == Necessity.REQUIRED


def test_preferred_necessity():
    requirement = make_requirement(
        original_text="Experience with Kubernetes is a plus",
        necessity=Necessity.PREFERRED,
        concept_id="unresolved:kubernetes",
    )
    assert requirement.necessity == Necessity.PREFERRED


def test_necessity_has_exactly_two_states():
    assert {n.value for n in Necessity} == {"required", "preferred"}


# ---------------------------------------------------------------------------
# Importance (ordinal, independent of necessity)
# ---------------------------------------------------------------------------

def test_importance_levels_are_ordered():
    assert Importance.LOW < Importance.MEDIUM < Importance.HIGH


def test_importance_and_necessity_are_independent_axes():
    # Both Git and Python can be REQUIRED, while the job emphasizes
    # Python (HIGH) far more heavily than Git (LOW).
    python_req = make_requirement(
        original_text="Python", necessity=Necessity.REQUIRED, importance=Importance.HIGH,
        concept_id="language.python",
    )
    git_req = make_requirement(
        original_text="Git", necessity=Necessity.REQUIRED, importance=Importance.LOW,
        concept_id="unresolved:git",
    )
    assert python_req.necessity == git_req.necessity == Necessity.REQUIRED
    assert python_req.importance > git_req.importance


# ---------------------------------------------------------------------------
# GitHub observability
# ---------------------------------------------------------------------------

def test_observability_has_three_ordered_levels():
    assert (
        GithubObservability.NOT_OBSERVABLE
        < GithubObservability.PARTIALLY_OBSERVABLE
        < GithubObservability.STRONGLY_OBSERVABLE
    )


def test_strongly_observable_technical_requirement():
    requirement = make_requirement(
        original_text="Uses React", concept_id="framework.react",
        github_observability=GithubObservability.STRONGLY_OBSERVABLE,
    )
    assert requirement.github_observability == GithubObservability.STRONGLY_OBSERVABLE


def test_partially_observable_requirement():
    requirement = make_requirement(
        original_text="Experience designing distributed systems",
        concept_id=None,
        category="practice",
        github_observability=GithubObservability.PARTIALLY_OBSERVABLE,
    )
    assert requirement.github_observability == GithubObservability.PARTIALLY_OBSERVABLE


def test_not_observable_requirement():
    requirement = make_requirement(
        original_text="Excellent communication skills",
        concept_id=None,
        category="soft_skill",
        github_observability=GithubObservability.NOT_OBSERVABLE,
    )
    assert requirement.github_observability == GithubObservability.NOT_OBSERVABLE


# ---------------------------------------------------------------------------
# Parser confidence (distinct from evidence.types.ConfidenceLevel)
# ---------------------------------------------------------------------------

def test_parser_confidence_is_optional_and_defaults_to_none():
    requirement = make_requirement()
    assert requirement.parser_confidence is None


def test_parser_confidence_can_be_set():
    requirement = make_requirement(parser_confidence=ParserConfidence.LOW)
    assert requirement.parser_confidence == ParserConfidence.LOW


def test_parser_confidence_is_a_distinct_type_from_evidence_confidence_level():
    from gitscore.evidence.types import ConfidenceLevel

    assert ParserConfidence is not ConfidenceLevel
    assert not issubclass(ParserConfidence, ConfidenceLevel)


def test_ambiguous_alternatives_example_is_representable():
    # "Experience with cloud platforms such as AWS or Azure" -- AWS/Azure
    # could be independent requirements, alternatives, or illustrative
    # examples. Milestone 6A only needs the LOW-confidence state to be
    # representable, not a real disambiguation policy.
    aws = make_requirement(
        original_text="Experience with cloud platforms such as AWS or Azure",
        concept_id="unresolved:aws",
        necessity=Necessity.PREFERRED,
        parser_confidence=ParserConfidence.LOW,
    )
    assert aws.parser_confidence == ParserConfidence.LOW


# ---------------------------------------------------------------------------
# Provenance (SourceSpan)
# ---------------------------------------------------------------------------

def test_requirement_without_source_span_is_valid():
    requirement = make_requirement()
    assert requirement.source_span is None


def test_requirement_with_source_span():
    span = SourceSpan(start=10, end=37)
    requirement = make_requirement(source_span=span)
    assert requirement.source_span == span
    assert requirement.source_span.start == 10
    assert requirement.source_span.end == 37


def test_source_span_rejects_negative_start():
    with pytest.raises(ValueError):
        SourceSpan(start=-1, end=5)


def test_source_span_rejects_end_not_after_start():
    with pytest.raises(ValueError):
        SourceSpan(start=5, end=5)
    with pytest.raises(ValueError):
        SourceSpan(start=5, end=3)


def test_source_span_is_frozen_and_hashable():
    span = SourceSpan(start=0, end=5)
    with pytest.raises(dataclasses.FrozenInstanceError):
        span.start = 1
    assert hash(span) == hash(SourceSpan(start=0, end=5))


# ---------------------------------------------------------------------------
# Invalid states (Part 11)
# ---------------------------------------------------------------------------

def test_empty_original_text_is_rejected():
    with pytest.raises(ValueError):
        make_requirement(original_text="")


def test_whitespace_only_original_text_is_rejected():
    with pytest.raises(ValueError):
        make_requirement(original_text="   ")


def test_whitespace_only_concept_id_is_rejected():
    with pytest.raises(ValueError):
        make_requirement(concept_id="   ")


# ---------------------------------------------------------------------------
# Milestone 6A.1: concept_id invariant -- the three intended states
# (None / registered canonical id / valid unresolved:<term> id) are the
# ONLY accepted states; arbitrary strings are rejected at construction.
# ---------------------------------------------------------------------------

def test_concept_id_none_is_valid():
    requirement = make_requirement(concept_id=None)
    assert requirement.concept_id is None
    assert not requirement.is_technical


def test_concept_id_registered_canonical_id_is_valid():
    requirement = make_requirement(concept_id=resolve_concept("PostgreSQL").concept_id)
    assert requirement.concept_id == "database.postgresql"
    assert requirement.is_resolved_concept


def test_concept_id_valid_unresolved_id_is_valid():
    requirement = make_requirement(concept_id=resolve_concept("warp-level primitives").concept_id)
    assert requirement.concept_id == "unresolved:warp-level_primitives"
    assert requirement.is_unresolved_concept


def test_concept_id_empty_string_is_rejected():
    with pytest.raises(ValueError):
        make_requirement(concept_id="")


def test_concept_id_whitespace_only_is_rejected():
    with pytest.raises(ValueError):
        make_requirement(concept_id="   ")


def test_concept_id_malformed_unresolved_id_is_rejected():
    with pytest.raises(ValueError):
        make_requirement(concept_id="unresolved:")
    with pytest.raises(ValueError):
        make_requirement(concept_id="unresolved:   ")


def test_concept_id_arbitrary_nonexistent_canonical_looking_id_is_rejected():
    # Must not silently masquerade as a resolved concept (the bug this
    # review exists to catch).
    with pytest.raises(ValueError):
        make_requirement(concept_id="whatever.random.string")
    with pytest.raises(ValueError):
        make_requirement(concept_id="language.does_not_exist")
    with pytest.raises(ValueError):
        make_requirement(concept_id="garbage")


def test_concept_id_arbitrary_string_is_rejected_even_if_registry_looking():
    # JobRequirement never performs resolution -- a raw human-typed alias
    # is not itself a valid concept_id, even though resolve_concept()
    # would happily match it.
    assert resolve_concept("Postgres").matched
    with pytest.raises(ValueError):
        make_requirement(concept_id="Postgres")


def test_postgres_and_pytorch_resolution_examples_are_unchanged_by_the_tightened_invariant():
    postgres = make_requirement(concept_id=resolve_concept("Postgres").concept_id)
    pytorch = make_requirement(
        original_text="Experience with PyTorch", concept_id=resolve_concept("PyTorch").concept_id
    )
    assert postgres.concept_id == "database.postgresql"
    assert pytorch.concept_id == "ml.framework.pytorch"


def test_compound_requirement_example_is_unchanged_by_the_tightened_invariant():
    sentence = "3+ years of experience building Python backend services"
    technical = make_requirement(
        original_text=sentence,
        concept_id=resolve_concept("Python").concept_id,
        github_observability=GithubObservability.STRONGLY_OBSERVABLE,
    )
    non_technical = make_requirement(
        original_text=sentence, concept_id=None, github_observability=GithubObservability.NOT_OBSERVABLE
    )
    assert technical.concept_id == "language.python"
    assert non_technical.concept_id is None


def test_whitespace_only_category_is_rejected():
    with pytest.raises(ValueError):
        make_requirement(category="   ")


def test_none_concept_id_is_a_valid_non_technical_state():
    # Must not be confused with the malformed-empty-string case above.
    requirement = make_requirement(concept_id=None)
    assert requirement.concept_id is None


# ---------------------------------------------------------------------------
# Immutability / equality / hashing
# ---------------------------------------------------------------------------

def test_job_requirement_is_frozen():
    requirement = make_requirement()
    with pytest.raises(dataclasses.FrozenInstanceError):
        requirement.necessity = Necessity.PREFERRED


def test_job_requirement_equality_and_hash_are_structural():
    a = make_requirement()
    b = make_requirement()
    c = make_requirement(original_text="A different requirement entirely")

    assert a == b
    assert hash(a) == hash(b)
    assert len({a, b, c}) == 2


def test_job_requirement_with_different_source_span_is_a_distinct_object():
    a = make_requirement(source_span=SourceSpan(0, 5))
    b = make_requirement(source_span=SourceSpan(10, 15))
    assert a != b
