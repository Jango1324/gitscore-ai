"""Milestone 5C: gitscore.concepts (TechnicalConcept, registry, resolve_concept)."""
from gitscore.concepts import (
    CONCEPT_REGISTRY_VERSION,
    ConceptRegistry,
    TechnicalConcept,
    default_registry,
    is_unresolved_concept_id,
    is_valid_concept_id,
    normalize_term,
    resolve_concept,
    unresolved_concept_id,
)


# ---------------------------------------------------------------------------
# Stable IDs / registry shape
# ---------------------------------------------------------------------------

def test_registry_has_stable_concept_ids_for_every_representative_concept():
    registry = default_registry()
    ids = {c.concept_id for c in registry.all_concepts()}

    for expected in [
        "language.python",
        "database.postgresql",
        "ml.framework.pytorch",
        "robotics.ros2",
        "platform.cuda",
        "infra.docker",
        "embedded.rtos.freertos",
        "hdl.verilog",
        "framework.react",
        "database.redis",
        "cloud.aws",
        "toolchain.llvm",
    ]:
        assert expected in ids


def test_get_by_concept_id_returns_the_concept():
    registry = default_registry()
    concept = registry.get("database.postgresql")
    assert concept.display_name == "PostgreSQL"
    assert concept.category == "database"


def test_get_unknown_concept_id_returns_none_not_an_exception():
    assert default_registry().get("nonexistent.concept") is None


def test_registry_spans_multiple_categories_not_just_one_domain():
    categories = {c.category for c in default_registry().all_concepts()}
    # Proves the mechanism generalizes past "ML" -- at least a handful of
    # distinct categories represented in the small starter set.
    assert len(categories) >= 6


# ---------------------------------------------------------------------------
# Alias resolution, case + punctuation normalization
# ---------------------------------------------------------------------------

def test_case_insensitive_alias_resolution():
    for term in ["Postgres", "postgresql", "POSTGRESQL", "PostgreSQL"]:
        result = resolve_concept(term)
        assert result.matched
        assert result.concept.concept_id == "database.postgresql"


def test_punctuation_normalization_for_react():
    for term in ["React.js", "ReactJS", "react"]:
        result = resolve_concept(term)
        assert result.matched
        assert result.concept.concept_id == "framework.react"


def test_pytorch_aliases():
    for term in ["torch", "PyTorch", "pytorch"]:
        result = resolve_concept(term)
        assert result.matched
        assert result.concept.concept_id == "ml.framework.pytorch"


def test_multi_word_alias_normalization_for_aws():
    for term in ["AWS", "Amazon Web Services", "amazon web services"]:
        result = resolve_concept(term)
        assert result.matched
        assert result.concept.concept_id == "cloud.aws"


def test_normalize_term_strips_periods_commas_and_collapses_whitespace():
    assert normalize_term("React.js") == "reactjs"
    assert normalize_term("  Amazon   Web Services  ") == "amazon web services"
    assert normalize_term("PostgreSQL") == "postgresql"


def test_normalization_does_not_collapse_distinct_concepts():
    # A blanket "strip everything non-alphanumeric" normalizer would risk
    # this kind of collision; the narrow punctuation-only rule must not.
    assert normalize_term("C++") != normalize_term("C")


# ---------------------------------------------------------------------------
# Unknown concept behavior (Milestone 5C Part 3)
# ---------------------------------------------------------------------------

def test_unknown_term_is_explicitly_unmatched_not_silently_accepted():
    result = resolve_concept("some-new-framework")
    assert result.matched is False
    assert result.concept is None


def test_unknown_term_still_produces_a_usable_concept_id():
    result = resolve_concept("some-new-framework")
    assert result.concept_id == "unresolved:some-new-framework"
    assert is_unresolved_concept_id(result.concept_id)


def test_unresolved_concept_id_is_deterministic_for_the_same_term():
    assert unresolved_concept_id("Some New Framework") == unresolved_concept_id("some new framework")


def test_unresolved_concept_id_does_not_merge_different_unknown_terms():
    # Two different spellings of an unknown concept are NOT fuzzy-merged --
    # that would require the ontology-building work explicitly out of scope.
    assert unresolved_concept_id("some-new-framework") != unresolved_concept_id("SomeNewFramework")


def test_resolving_an_unknown_term_does_not_mutate_the_shared_registry():
    registry = default_registry()
    before = len(registry.all_concepts())

    resolve_concept("totally-unknown-thing-xyz")
    resolve_concept("another-unknown-thing")

    after = len(registry.all_concepts())
    assert after == before
    assert registry.get("unresolved:totally-unknown-thing-xyz") is None


def test_default_registry_is_a_stable_shared_instance():
    assert default_registry() is default_registry()


# ---------------------------------------------------------------------------
# Milestone 6A.1: is_valid_concept_id -- VALIDATION of an already-produced
# id, never RESOLUTION of raw text.
# ---------------------------------------------------------------------------

def test_is_valid_concept_id_true_for_a_real_registered_id():
    assert is_valid_concept_id("language.python")
    assert is_valid_concept_id("database.postgresql")
    assert is_valid_concept_id("ml.framework.pytorch")


def test_is_valid_concept_id_true_for_a_well_formed_unresolved_id():
    assert is_valid_concept_id(unresolved_concept_id("warp-level primitives"))
    assert is_valid_concept_id("unresolved:python")  # well-formed, even if "python" is separately resolvable
    assert is_valid_concept_id(unresolved_concept_id("kubernetes"))


def test_is_valid_concept_id_false_for_empty_or_whitespace_unresolved_suffix():
    assert not is_valid_concept_id("unresolved:")
    assert not is_valid_concept_id("unresolved:   ")


def test_is_valid_concept_id_false_for_arbitrary_nonexistent_canonical_looking_id():
    # Dotted, canonical-looking, but never actually registered -- must
    # NOT silently masquerade as a resolved concept.
    assert not is_valid_concept_id("language.does_not_exist")
    assert not is_valid_concept_id("whatever.random.string")
    assert not is_valid_concept_id("garbage")


def test_is_valid_concept_id_false_for_empty_or_whitespace_string():
    assert not is_valid_concept_id("")
    assert not is_valid_concept_id("   ")
    assert not is_valid_concept_id(" language.python")  # padding is also malformed


def test_is_valid_concept_id_never_resolves_a_raw_human_typed_term():
    # is_valid_concept_id answers "is this ALREADY a valid id", not
    # "what concept does this term mean" -- that is resolve_concept()'s
    # job. A raw alias is not itself a valid concept_id.
    assert resolve_concept("Postgres").matched
    assert not is_valid_concept_id("Postgres")
    assert not is_valid_concept_id("postgres")


def test_is_valid_concept_id_accepts_an_explicit_registry():
    custom = ConceptRegistry(
        [TechnicalConcept(concept_id="custom.thing", display_name="Thing", category="custom", aliases=("thing",))]
    )
    assert is_valid_concept_id("custom.thing", registry=custom)
    assert not is_valid_concept_id("custom.thing")  # not in the default registry
    assert not is_valid_concept_id("language.python", registry=custom)  # not in the custom one


# ---------------------------------------------------------------------------
# A caller-provided registry is honored (no hidden global dependency)
# ---------------------------------------------------------------------------

def test_resolve_concept_accepts_an_explicit_registry():
    custom = ConceptRegistry(
        [TechnicalConcept(concept_id="custom.thing", display_name="Thing", category="custom", aliases=("thing",))]
    )
    result = resolve_concept("thing", registry=custom)
    assert result.matched
    assert result.concept.concept_id == "custom.thing"

    # And does NOT leak into the default registry.
    assert default_registry().get("custom.thing") is None


# ---------------------------------------------------------------------------
# Milestone 5D.1: source-aware alias safety (readme_unsafe_aliases /
# readme_safe_aliases())
# ---------------------------------------------------------------------------

def test_readme_safe_aliases_defaults_to_all_aliases_when_none_marked_unsafe():
    concept = TechnicalConcept(
        concept_id="custom.thing", display_name="Thing", category="custom", aliases=("thing", "thingy")
    )
    assert concept.readme_safe_aliases() == ("thing", "thingy")


def test_readme_safe_aliases_excludes_marked_unsafe_aliases():
    concept = TechnicalConcept(
        concept_id="custom.thing",
        display_name="Thing",
        category="custom",
        aliases=("go", "golang"),
        readme_unsafe_aliases=frozenset({"go"}),
    )
    assert concept.readme_safe_aliases() == ("golang",)


def test_readme_safe_aliases_is_empty_when_every_alias_is_unsafe():
    concept = TechnicalConcept(
        concept_id="custom.thing",
        display_name="Thing",
        category="custom",
        aliases=("c",),
        readme_unsafe_aliases=frozenset({"c"}),
    )
    assert concept.readme_safe_aliases() == ()


def test_readme_unsafe_alias_not_present_in_aliases_raises():
    import pytest

    with pytest.raises(ValueError):
        TechnicalConcept(
            concept_id="custom.thing",
            display_name="Thing",
            category="custom",
            aliases=("thing",),
            readme_unsafe_aliases=frozenset({"typo"}),
        )


def test_registry_concepts_marked_readme_unsafe_still_resolve_via_resolve_concept():
    # "go", "next", "js", "ts", "c" stay valid resolve_concept() aliases
    # for structured sources (dependency manifests, language stats) --
    # only evidence/extraction/readme.py restricts itself further.
    for term, expected_id in [
        ("go", "language.go"),
        ("next", "framework.nextjs"),
        ("js", "language.javascript"),
        ("ts", "language.typescript"),
        ("c", "language.c"),
    ]:
        result = resolve_concept(term)
        assert result.matched
        assert result.concept.concept_id == expected_id


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

def test_concept_registry_version_constant_exists_and_is_an_int():
    # Bumped to 2 in Milestone 5D: new concepts added (languages.py's
    # GitHub-language set, plus a handful of dependency-manifest-only
    # concepts) -- see registry.py's versioning policy and
    # docs/CHANGELOG_DEV.md's Milestone 5D entry.
    # Bumped to 3 in Milestone 5D.1: `readme_unsafe_aliases` added to
    # several existing concepts (go/next/js/ts/c) -- a registry-content
    # change per registry.py's own bump policy, even though it doesn't
    # change what resolve_concept() itself matches. See
    # docs/CHANGELOG_DEV.md's Milestone 5D.1 entry.
    # Bumped to 4 in Milestone 8D.1: Kubernetes, generic SQL, Swift,
    # Kotlin, and `framework.react_native` added -- see
    # docs/CHANGELOG_DEV.md's Milestone 8D.1 entry.
    assert isinstance(CONCEPT_REGISTRY_VERSION, int)
    assert CONCEPT_REGISTRY_VERSION == 4
