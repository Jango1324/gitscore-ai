"""Milestone 9B Phase 1 -- tests for the preservation-benchmark TOOLING
(`scripts/evaluation_lib/preservation_eval.py` and
`evaluation/m9b/corpus.json`'s own structural integrity), not for how
many entries the real parser currently passes -- that is a measurement
reported by `scripts/evaluate_m9b_preservation.py`, not a test
assertion (mirroring `tests/test_evaluation_harness.py`'s own stated
policy for the 8c:v1 harness).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from evaluation_lib import preservation_eval as pe

CORPUS_PATH = REPO_ROOT / "evaluation" / "m9b" / "corpus.json"


def _load_corpus() -> dict:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Corpus structural integrity
# ---------------------------------------------------------------------------


def test_corpus_file_loads_and_has_entries():
    corpus = _load_corpus()
    assert corpus["corpus_version"] == "9b:v1"
    assert len(corpus["entries"]) >= 25


def test_every_entry_has_a_unique_id():
    corpus = _load_corpus()
    ids = [e["id"] for e in corpus["entries"]]
    assert len(ids) == len(set(ids))


def test_every_entry_declares_its_annotation_independently_of_the_parser():
    """Structural guard, not a semantic one: every entry must declare
    is_requirement/is_technical/ideal_outcome BEFORE any parser call --
    enforced here by requiring the fields exist and are never derived
    from a field name that would imply a parser run (e.g. no entry may
    carry a field literally named 'actual_parser_output' or similar).
    """
    corpus = _load_corpus()
    forbidden_keys = {"actual_parser_output", "parsed_result", "observed_output"}
    for entry in corpus["entries"]:
        assert forbidden_keys.isdisjoint(entry.keys()), entry["id"]
        assert "is_requirement" in entry and isinstance(entry["is_requirement"], bool)
        assert "is_technical" in entry and isinstance(entry["is_technical"], bool)
        assert "ideal_outcome" in entry
        assert entry["wrapping"] in pe._WRAPPERS


def test_every_wrapping_kind_used_by_the_corpus_is_implemented():
    corpus = _load_corpus()
    used = {e["wrapping"] for e in corpus["entries"]}
    assert used <= set(pe._WRAPPERS)


def test_corpus_covers_every_required_category():
    """The Milestone 9B brief names specific coverage categories -- this
    pins that the corpus actually contains at least one entry for each,
    so a future edit cannot silently drop a required category.
    """
    required_categories = {
        "registered_technical_concept",
        "unregistered_named_technology",
        "unknown_single_term",
        "unknown_and_list",
        "unknown_or_group",
        "mixed_known_and_unknown",
        "technical_competency_no_named_product",
        "professional_experience",
        "education",
        "certification",
        "soft_skill",
        "non_requirement_prose",
        "heading_or_section_intro",
        "ambiguous_language",
    }
    corpus = _load_corpus()
    present = {e["category"] for e in corpus["entries"]}
    missing = required_categories - present
    assert not missing, f"corpus is missing required categories: {missing}"


# ---------------------------------------------------------------------------
# wrap_entry()
# ---------------------------------------------------------------------------


def test_wrap_entry_preserves_the_exact_source_text():
    entry = {"wrapping": "requirements_bullet", "source_text": "Experience with Terraform"}
    wrapped = pe.wrap_entry(entry)
    assert "Experience with Terraform" in wrapped
    assert wrapped.startswith("Requirements:")


def test_wrap_entry_rejects_an_unknown_wrapping_kind():
    import pytest

    with pytest.raises(ValueError):
        pe.wrap_entry({"id": "unit-test-003", "wrapping": "not_a_real_kind", "source_text": "x"})


# ---------------------------------------------------------------------------
# Classification logic -- pinned against hand-built JobRequirement rows,
# never against the real parser's current output (that would make these
# tests describe today's bugs instead of the intended ALGORITHM).
# ---------------------------------------------------------------------------


def _make_requirement(**kwargs):
    from gitscore.jobs import JobRequirement, SourceSpan
    from gitscore.jobs.types import GithubObservability, Importance, Necessity

    defaults = dict(
        original_text="Experience with Python",
        necessity=Necessity.REQUIRED,
        importance=Importance.MEDIUM,
        github_observability=GithubObservability.STRONGLY_OBSERVABLE,
        source_span=SourceSpan(0, 23),
    )
    defaults.update(kwargs)
    return JobRequirement(**defaults)


def test_matches_ideal_recognized_concepts_requires_exact_id_set():
    row = _make_requirement(concept_id="language.python")
    ideal = {"type": "recognized_concepts", "concept_ids": ["language.python"], "github_observability": "strongly_observable"}
    assert pe._matches_ideal([row], ideal) is True

    other = {"type": "recognized_concepts", "concept_ids": ["language.go"], "github_observability": "strongly_observable"}
    assert pe._matches_ideal([row], other) is False


def test_matches_ideal_unresolved_alternative_group_requires_exact_sorted_ids():
    from gitscore.jobs.types import GithubObservability, Importance, Necessity

    row = _make_requirement(
        concept_id=None, alternative_concept_ids=("unresolved:angular", "unresolved:vue"),
        necessity=Necessity.PREFERRED, importance=Importance.LOW,
        github_observability=GithubObservability.STRONGLY_OBSERVABLE,
    )
    ideal = {"type": "unresolved_alternative_group", "concept_ids": ["unresolved:vue", "unresolved:angular"]}
    assert pe._matches_ideal([row], ideal) is True


def test_matches_fallback_silent_drop_is_true_only_for_zero_rows():
    assert pe._matches_fallback([], {"type": "silent_drop"}) is True
    row = _make_requirement(concept_id="language.python")
    assert pe._matches_fallback([row], {"type": "silent_drop"}) is False


def test_has_fabricated_concept_flags_a_real_wrong_id_not_an_unresolved_one():
    ideal = {"type": "non_technical", "category": "soft_skill"}
    fabricated_row = _make_requirement(concept_id="language.python", category="language")
    assert pe._has_fabricated_concept([fabricated_row], ideal, is_technical=False) is True

    unresolved_row = _make_requirement(concept_id="unresolved:something", category=None)
    assert pe._has_fabricated_concept([unresolved_row], ideal, is_technical=False) is False


def test_evaluate_entry_on_a_known_good_registered_concept_claim_is_ideal_match():
    entry = {
        "id": "unit-test-001",
        "category": "registered_technical_concept",
        "source_text": "Strong experience with Python and PostgreSQL",
        "wrapping": "requirements_bullet",
        "is_requirement": True,
        "is_technical": True,
        "ideal_outcome": {
            "type": "recognized_concepts",
            "concept_ids": ["language.python", "database.postgresql"],
            "github_observability": "strongly_observable",
        },
        "acceptable_fallback": None,
    }
    verdict = pe.evaluate_entry(entry)
    assert verdict.verdict == pe.IDEAL_MATCH
    assert verdict.span_correct is True


def test_evaluate_entry_on_excluded_prose_with_no_rows_is_correctly_excluded():
    entry = {
        "id": "unit-test-002",
        "category": "non_requirement_prose",
        "source_text": "We are a passionate team building delightful products.",
        "wrapping": "intro_prose",
        "is_requirement": False,
        "is_technical": False,
        "ideal_outcome": {"type": "excluded"},
        "acceptable_fallback": None,
    }
    verdict = pe.evaluate_entry(entry)
    assert verdict.verdict == pe.CORRECTLY_EXCLUDED
    assert verdict.span_correct is None


# ---------------------------------------------------------------------------
# aggregate_metrics(): keeps placeholder-success and fabrication as
# DISTINCT counts, never merged (Milestone 9B's explicit instruction).
# ---------------------------------------------------------------------------


def test_aggregate_metrics_never_merges_placeholder_with_fabrication():
    corpus = _load_corpus()
    entries = corpus["entries"]
    entries_by_id = {e["id"]: e for e in entries}
    report = pe.evaluate_corpus(entries)
    metrics = pe.aggregate_metrics(report, entries_by_id)

    assert "5_correct_unparsed_placeholder_preservation" in metrics["metrics"]
    assert "7_incorrect_technology_fabrication" in metrics["metrics"]
    # Different shapes on purpose -- metric 5 is a rate (numerator/denominator
    # over placeholder-relevant entries), metric 7 is a raw count over the
    # WHOLE corpus. Conflating them into one number is exactly what the
    # brief prohibits; this pins that they stay structurally different.
    assert "numerator" in metrics["metrics"]["5_correct_unparsed_placeholder_preservation"]
    assert "numerator" not in metrics["metrics"]["7_incorrect_technology_fabrication"]


def test_aggregate_metrics_silent_drop_count_is_split_not_combined():
    corpus = _load_corpus()
    entries = corpus["entries"]
    entries_by_id = {e["id"]: e for e in entries}
    report = pe.evaluate_corpus(entries)
    metrics = pe.aggregate_metrics(report, entries_by_id)

    value = metrics["metrics"]["9_silent_drop_count"]["value"]
    assert set(value) == {"accepted_by_corpus", "flagged_as_gap"}
