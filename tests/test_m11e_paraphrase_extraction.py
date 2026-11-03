"""Milestone 11-E -- v2 paraphrase-tolerant competency extractor tests.

Covers: paraphrase/alias recognition (semantically_equivalent and
narrower_or_more_specific, with correct ParserConfidence
differentiation), RELATED_ONLY/UNKNOWN correct non-recognition,
grammatical-variant tolerance (plurals, "-ing"/"-ic" suffixes),
preservation of every v1 safety behavior (rejection filters,
missing-contract decline, MIXED_UNSUPPORTED, applicability routing,
AND-splitting), determinism, and non-regression of v1 itself.
"""
from __future__ import annotations

import pytest

from gitscore.jobs.models import SourceSpan
from gitscore.jobs.parsing.competency_extraction import (
    DeclinedExtraction,
    extract_competency_qualifications,
    extract_competency_qualifications_v2,
)
from gitscore.jobs.parsing.qualification import LogicalComposition, QualificationKind, project_qualification
from gitscore.jobs.types import Necessity, ParserConfidence


def _extract_v2(text: str):
    return extract_competency_qualifications_v2(text, SourceSpan(0, len(text)))


# ---------------------------------------------------------------------------
# Paraphrase (semantically_equivalent alias) recognition, at HIGH confidence.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected_tag",
    [
        ("Solid grasp of DS&A is required.", "algorithms-data-structures"),
        ("Strong thread-safety fundamentals are required.", "concurrency"),
        ("Strong background in distributed computing is preferred.", "distributed-systems"),
        ("Strong software architecture skills are required.", "system-design"),
        ("Strong performance tuning skills are required.", "performance-optimization"),
    ],
)
def test_semantically_equivalent_alias_recognized_at_high_confidence(text, expected_tag):
    [q] = _extract_v2(text)
    assert q.normalized_reference.competency_tag == expected_tag
    assert q.interpretation_certainty == ParserConfidence.HIGH


# ---------------------------------------------------------------------------
# Narrower-or-more-specific alias recognition, at MEDIUM confidence.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected_tag",
    [
        ("RTOS development experience is required.", "embedded-systems-design"),
        ("Kernel development experience is preferred.", "os-networking"),
        ("Incident response experience is required.", "cybersecurity-threat-modeling"),
        ("FPGA programming experience is preferred.", "digital-logic"),
    ],
)
def test_narrower_alias_recognized_at_medium_confidence(text, expected_tag):
    [q] = _extract_v2(text)
    assert q.normalized_reference.competency_tag == expected_tag
    assert q.interpretation_certainty == ParserConfidence.MEDIUM


# ---------------------------------------------------------------------------
# RELATED_ONLY / UNKNOWN terms never silently promoted.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Competitive programming experience is a plus.",
        "Database administration experience is a plus.",
        "Data science experience is required.",
        "PCB layout experience is required.",
        "IoT development experience is a plus.",
    ],
)
def test_related_only_terms_are_declined_not_mapped(text):
    result = _extract_v2(text)
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "no_competency_language"


def test_distributed_computing_resolves_to_distributed_systems_never_concurrency():
    [q] = _extract_v2("Distributed computing experience is required.")
    assert q.normalized_reference.competency_tag == "distributed-systems"
    assert q.normalized_reference.competency_tag != "concurrency"


def test_out_of_taxonomy_domain_is_declined():
    result = _extract_v2("Strong mechanical CAD and finite element analysis skills are required.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "no_competency_language"


# ---------------------------------------------------------------------------
# Grammatical-variant tolerance (the core paraphrase-generalization target).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected_tag",
    [
        ("Strong algorithmic skills are required.", "algorithms-data-structures"),
        ("Experience with a distributed system of this scale is required.", "distributed-systems"),
        ("Solid databases design knowledge is required.", "database-design"),
        ("Strong performance optimizations background is required.", "performance-optimization"),
    ],
)
def test_grammatical_variants_are_recognized(text, expected_tag):
    [q] = _extract_v2(text)
    assert q.normalized_reference.competency_tag == expected_tag


def test_v1_does_not_recognize_the_same_grammatical_variant_v2_does():
    """Confirms v2 is a genuine IMPROVEMENT over v1, not a redundant
    reimplementation -- v1's own exact-phrase vocabulary has no alias
    for 'algorithmic skills' and no stemming, so it must decline here."""
    text = "Strong algorithmic skills are required."
    v1_result = extract_competency_qualifications(text, SourceSpan(0, len(text)))
    assert isinstance(v1_result, DeclinedExtraction)
    v2_result = _extract_v2(text)
    assert not isinstance(v2_result, DeclinedExtraction)


# ---------------------------------------------------------------------------
# Every v1 safety behavior preserved.
# ---------------------------------------------------------------------------


def test_negation_still_declined_in_v2():
    result = _extract_v2("No prior experience with distributed systems is necessary -- we will train you.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "negation"


def test_responsibility_lead_without_qualifying_intent_is_declined_regardless_of_reason():
    """A bare duty bullet with no qualifying-intent phrase never reaches
    v2's own vocabulary matcher at all (the intent gate rejects it
    first) -- a different, EARLIER safe decline than v1's own explicit
    `responsibility_lead` reason, but still never a fabricated qualification."""
    result = _extract_v2("Design and implement control systems for autonomous vehicles.")
    assert isinstance(result, DeclinedExtraction)


def test_explicit_responsibility_lead_filter_still_fires_when_intent_gate_would_otherwise_pass():
    """Exercises the EXPLICIT `_RESPONSIBILITY_LEAD` rejection filter
    itself (not merely the earlier intent gate) by using a duty bullet
    that ALSO happens to contain a qualifying-intent word ("deep")."""
    result = _extract_v2("Debug and optimize performance-critical systems with deep concurrency expertise.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "responsibility_lead"


def test_missing_contract_still_declines_in_v2():
    result = _extract_v2(
        "Experience with at least one of the following: distributed systems, concurrency, or performance optimization."
    )
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "missing_contract"


def test_mixed_unsupported_still_detected_in_v2():
    result = _extract_v2(
        "Experience with system design, and familiarity with either distributed systems or performance optimization."
    )
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.logical_composition == LogicalComposition.MIXED_UNSUPPORTED
    assert project_qualification(q).job_requirement is None


def test_unknown_necessity_still_preserved_not_fabricated_in_v2():
    [q] = _extract_v2("Experience debugging and optimizing performance-critical code paths.")
    assert q.necessity is None
    result = project_qualification(q)
    assert result.job_requirement is None
    assert result.unsafe_reason == "necessity_unknown"


def test_applicability_condition_still_routes_safely_in_v2():
    text = "Firmware development experience is required, if the role requires low-level hardware access."
    [q] = _extract_v2(text)
    assert q.applicability_condition is not None
    result = project_qualification(q)
    assert result.job_requirement is None
    assert result.unparsed_claim.text == text


def test_and_of_distinct_areas_still_splits_into_siblings_in_v2():
    result = _extract_v2("Required: strong skills in concurrency, system design, and database design.")
    assert not isinstance(result, DeclinedExtraction)
    tags = {q.normalized_reference.competency_tag for q in result}
    assert tags == {"concurrency", "system-design", "database-design"}
    assert all(q.logical_composition == LogicalComposition.AND for q in result)


def test_github_observability_never_strongly_observable_in_v2():
    [q] = _extract_v2("Strong foundation in circuit theory is required.")
    from gitscore.jobs.types import GithubObservability
    assert q.github_observability != GithubObservability.STRONGLY_OBSERVABLE


# ---------------------------------------------------------------------------
# Determinism and non-regression.
# ---------------------------------------------------------------------------


def test_v2_is_deterministic():
    text = "Required: strong skills in concurrency, system design, and database design."
    a = _extract_v2(text)
    b = _extract_v2(text)
    assert a == b


def test_v1_function_is_completely_unmodified_by_v2s_presence():
    """v1's own exact-phrase behavior for a canonical phrase must be
    identical whether or not v2 exists in the same module."""
    text = "Strong understanding of algorithms and data structures is required."
    [q1] = extract_competency_qualifications(text, SourceSpan(0, len(text)))
    [q2] = _extract_v2(text)
    assert q1.normalized_reference.competency_tag == q2.normalized_reference.competency_tag == "algorithms-data-structures"


def test_module_still_not_imported_by_the_live_parser():
    import gitscore.jobs.parsing.narrative as narrative_module
    import gitscore.jobs.parsing.necessity as necessity_module
    import gitscore.jobs.parsing.parser as parser_module
    import gitscore.jobs.parsing.segmentation as segmentation_module

    for module in (parser_module, segmentation_module, necessity_module, narrative_module):
        assert "competency_extraction" not in module.__dict__
        assert "competency_aliases" not in module.__dict__


def test_parser_version_unchanged():
    from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION
    assert JOB_DESCRIPTION_PARSER_VERSION == "job_description_parser:v10"
