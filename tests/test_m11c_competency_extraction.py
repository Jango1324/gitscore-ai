"""Milestone 11-C Phase 4/5 -- offline competency extractor tests.

Covers: technical-competency recognition, rejection of narrative/
responsibility/learning/negated text, necessity preservation (including
genuinely unknown), AND-splitting into siblings, the OR_ANY
missing-contract decline, MIXED_UNSUPPORTED detection, applicability-
condition safety routing, GitHub-observability policy, source-span
exactness, determinism, and the Phase 5 "technology does not prove
competency" boundary (via the module's own total independence from any
technology-mention detector).
"""
from __future__ import annotations

import pytest

from gitscore.jobs.models import SourceSpan
from gitscore.jobs.parsing.competency_extraction import (
    DeclinedExtraction,
    extract_competency_qualifications,
)
from gitscore.jobs.parsing.qualification import LogicalComposition, QualificationKind, project_qualification
from gitscore.jobs.types import GithubObservability, Necessity


def _extract(text: str):
    return extract_competency_qualifications(text, SourceSpan(0, len(text)))


# ---------------------------------------------------------------------------
# Recognition across disciplines.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected_tag",
    [
        ("Strong understanding of algorithms and data structures is required.", "algorithms-data-structures"),
        ("Experience with concurrency and race conditions is required.", "concurrency"),
        ("Deep knowledge of distributed systems is required.", "distributed-systems"),
        ("Proven ability to design scalable system architecture is required.", "system-design"),
        ("Strong foundation in circuit theory is required.", "circuit-theory"),
        ("Experience with quantum circuit design is required.", "quantum-computing"),
    ],
)
def test_recognizes_competency_across_disciplines(text, expected_tag):
    result = _extract(text)
    assert not isinstance(result, DeclinedExtraction)
    [qualification] = result
    assert qualification.qualification_kind == QualificationKind.TECHNICAL_COMPETENCY
    assert qualification.normalized_reference.competency_tag == expected_tag


def test_no_competency_language_declines_with_the_correct_reason():
    result = _extract("Excellent communication skills are required.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "no_competency_language"


# ---------------------------------------------------------------------------
# Rejections: narrative, responsibility, learning, negation.
# ---------------------------------------------------------------------------


def test_company_narrative_is_rejected_not_extracted():
    result = _extract(
        "Our engineering team has deep expertise in distributed systems and has built "
        "some of the most resilient infrastructure in the industry."
    )
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "narrative_cue"


def test_broader_narrative_subject_is_rejected():
    result = _extract("We're a small team solving hard problems in computer vision and machine learning at scale.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "narrative_cue"


def test_responsibility_bullet_is_rejected_not_extracted():
    result = _extract("Design and implement distributed systems that scale to millions of users.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "responsibility_lead"


def test_learning_opportunity_is_rejected_via_existing_narrative_cue():
    result = _extract("You'll gain hands-on experience with distributed systems design and large-scale data processing.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "narrative_cue"


def test_negated_requirement_is_rejected_not_extracted():
    result = _extract("No prior experience with distributed systems is necessary -- we will train you.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "negation"


# ---------------------------------------------------------------------------
# Necessity: preserved, including genuinely unknown (never fabricated).
# ---------------------------------------------------------------------------


def test_required_necessity_is_recognized():
    [q] = _extract("Strong understanding of concurrency is required.")
    assert q.necessity == Necessity.REQUIRED


def test_preferred_necessity_is_recognized():
    [q] = _extract("Understanding of machine learning fundamentals is a plus.")
    assert q.necessity == Necessity.PREFERRED


def test_unknown_necessity_stays_none_never_fabricated():
    [q] = _extract("Experience debugging and optimizing performance-critical code paths.")
    assert q.necessity is None
    result = project_qualification(q)
    assert result.job_requirement is None
    assert result.unsafe_reason == "necessity_unknown"


# ---------------------------------------------------------------------------
# AND-splitting into siblings vs. single competency with descriptive terms.
# ---------------------------------------------------------------------------


def test_distinct_competency_areas_split_into_sibling_qualifications():
    result = _extract("Required: strong skills in concurrency, distributed systems, and database design.")
    assert not isinstance(result, DeclinedExtraction)
    tags = {q.normalized_reference.competency_tag for q in result}
    assert tags == {"concurrency", "distributed-systems", "database-design"}
    assert all(q.logical_composition == LogicalComposition.AND for q in result)
    assert all(q.necessity == Necessity.REQUIRED for q in result)


def test_one_competency_area_with_descriptive_subterms_stays_single():
    result = _extract("Deep knowledge of distributed systems, consensus algorithms, and fault tolerance is required.")
    assert not isinstance(result, DeclinedExtraction)
    assert len(result) == 1
    assert result[0].logical_composition == LogicalComposition.SINGLE
    assert result[0].normalized_reference.competency_tag == "distributed-systems"


# ---------------------------------------------------------------------------
# The missing-contract decline (OR_ANY group of competency tags).
# ---------------------------------------------------------------------------


def test_alternative_competency_group_declines_as_missing_contract():
    result = _extract(
        "Experience with at least one of the following: distributed systems, "
        "concurrent programming, or high-performance computing."
    )
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "missing_contract"
    assert "NormalizedReference" in result.detail


def test_missing_contract_never_silently_drops_the_option_list():
    """The decline's own detail text must name the actual tags found --
    confirming nothing was silently discarded even though no
    `Qualification` was produced."""
    result = _extract("Proficiency in one of the following areas: distributed systems, database internals, or operating systems.")
    assert isinstance(result, DeclinedExtraction)
    assert "distributed-systems" in result.detail
    assert "database-design" in result.detail
    assert "os-networking" in result.detail


# ---------------------------------------------------------------------------
# MIXED_UNSUPPORTED (AND of OR).
# ---------------------------------------------------------------------------


def test_mixed_and_or_structure_is_flagged_mixed_unsupported():
    result = _extract(
        "Experience with algorithms and data structures, and familiarity with "
        "either distributed systems or high-performance computing."
    )
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.logical_composition == LogicalComposition.MIXED_UNSUPPORTED
    assert q.normalized_reference is None
    result_projection = project_qualification(q)
    assert result_projection.job_requirement is None


# ---------------------------------------------------------------------------
# Applicability conditions route safely, never losing the condition text.
# ---------------------------------------------------------------------------


def test_conditional_competency_routes_to_unparsed_claim_condition_preserved():
    text = "Experience with GPU programming is required, unless you have equivalent experience with other forms of parallel computing."
    [q] = _extract(text)
    assert q.applicability_condition is not None
    assert "unless" in q.applicability_condition.lower()
    result = project_qualification(q)
    assert result.job_requirement is None
    assert result.unsafe_reason == "material_applicability_condition_not_representable_on_job_requirement"
    assert result.unparsed_claim.text == text


# ---------------------------------------------------------------------------
# GitHub observability policy -- never an evidence detector, a lookup only.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected_observability",
    [
        ("Strong foundation in circuit theory is required.", GithubObservability.NOT_OBSERVABLE),
        ("Understanding of machine learning fundamentals is required.", GithubObservability.NOT_OBSERVABLE),
        ("Experience with concurrency is required.", GithubObservability.PARTIALLY_OBSERVABLE),
        ("Experience with quantum circuit design is required.", GithubObservability.NOT_OBSERVABLE),
    ],
)
def test_observability_policy_never_claims_strongly_observable(text, expected_observability):
    [q] = _extract(text)
    assert q.github_observability == expected_observability
    assert q.github_observability != GithubObservability.STRONGLY_OBSERVABLE


# ---------------------------------------------------------------------------
# Source-span exactness.
# ---------------------------------------------------------------------------


def test_source_span_and_text_are_preserved_exactly():
    text = "Strong understanding of concurrency is required."
    span = SourceSpan(100, 100 + len(text))
    [q] = extract_competency_qualifications(text, span)
    assert q.source_text == text
    assert q.source_span is span


# ---------------------------------------------------------------------------
# Determinism.
# ---------------------------------------------------------------------------


def test_extraction_is_deterministic():
    text = "Required: strong skills in concurrency, distributed systems, and database design."
    result_a = _extract(text)
    result_b = _extract(text)
    assert result_a == result_b


# ---------------------------------------------------------------------------
# Not wired into the live parser.
# ---------------------------------------------------------------------------


def test_module_is_not_imported_by_the_live_parser():
    import gitscore.jobs.parsing.narrative as narrative_module
    import gitscore.jobs.parsing.necessity as necessity_module
    import gitscore.jobs.parsing.parser as parser_module
    import gitscore.jobs.parsing.segmentation as segmentation_module

    for module in (parser_module, segmentation_module, necessity_module, narrative_module):
        assert "competency_extraction" not in module.__dict__


def test_parser_version_unchanged():
    # Milestone 11-G6 bumped v10 -> v11, and M11-G7 subsequently bumped
    # v11 -> v12 (both unrelated, later, approved segmentation.py
    # fixes) -- this test's own purpose, confirming this milestone
    # itself never touched the version, is unaffected; only the
    # literal expected value tracks the current version.
    from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION
    # M11-G17 then bumped v12 -> v13 (alternatives.py compound AND/OR containment); this test's
    # own purpose is unaffected -- only the literal tracks the current version.
    assert JOB_DESCRIPTION_PARSER_VERSION == "job_description_parser:v13"
