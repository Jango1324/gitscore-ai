"""Milestone 11-G3 -- end-to-end offline qualification-understanding
pathway: segment_description() -> section provenance ->
extract_competency_qualifications_v2(..., has_section_context=True) ->
Qualification -> project_qualification() -> JobRequirement/UnparsedClaim.

This is a NEW, additive, offline evaluation harness -- it calls only
already-existing, unmodified functions (segment_description,
document_has_any_recognized_heading, extract_competency_qualifications_v2,
project_qualification) in a NEW combination. It does not call, modify,
or reroute `parse_job_description()`/`_parse()`/`_requirements_from_claim`
at all -- the live parser's own non-competency pathway is completely
untouched and independently unaffected by this module's existence.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gitscore.jobs.models import SourceSpan  # noqa: E402
from gitscore.jobs.parsing.competency_extraction import (  # noqa: E402
    DeclinedExtraction,
    extract_competency_qualifications_v2,
)
from gitscore.jobs.parsing.qualification import project_qualification  # noqa: E402
from gitscore.jobs.parsing.segmentation import (  # noqa: E402
    document_has_any_recognized_heading,
    segment_description,
)


def _run_pathway(description: str, target_text: str):
    claims = segment_description(description)
    doc_heading = document_has_any_recognized_heading(description)
    by_text = {c.text: c for c in claims}
    claim = by_text.get(target_text)
    if claim is None:
        return None, None, doc_heading
    span = SourceSpan(claim.start, claim.end)
    result = extract_competency_qualifications_v2(
        claim.text, span, section_kind=claim.section_kind,
        document_has_recognized_heading=doc_heading, has_section_context=True,
    )
    return claim, result, doc_heading


# ---------------------------------------------------------------------------
# REQUIRED/PREFERRED sections resolve correctly end-to-end.
# ---------------------------------------------------------------------------


def test_required_and_preferred_sections_resolve_correctly_end_to_end():
    description = (
        "Requirements:\nExperience with distributed systems is required.\n\n"
        "Preferred Qualifications:\nKnowledge of concurrency.\n"
    )
    _, required_result, _ = _run_pathway(description, "Experience with distributed systems is required.")
    _, preferred_result, _ = _run_pathway(description, "Knowledge of concurrency.")

    assert required_result[0].necessity.value.upper() == "REQUIRED"
    assert project_qualification(required_result[0]).job_requirement is not None

    assert preferred_result[0].necessity.value.upper() == "PREFERRED"
    assert project_qualification(preferred_result[0]).job_requirement is not None


# ---------------------------------------------------------------------------
# Responsibility duty, even one starting with a non-imperative verb and
# carrying qualifying-intent vocabulary, is never confidently scored.
# ---------------------------------------------------------------------------


def test_responsibility_duty_never_gets_a_confident_necessity_end_to_end():
    description = "Responsibilities:\nStrong ownership of distributed systems reliability.\n"
    _, result, _ = _run_pathway(description, "Strong ownership of distributed systems reliability.")
    assert not isinstance(result, DeclinedExtraction)
    assert result[0].necessity is None
    projection = project_qualification(result[0])
    assert projection.job_requirement is None
    assert projection.unsafe_reason == "necessity_unknown"


def test_responsibility_lead_shaped_duty_declines_outright_end_to_end():
    description = "Responsibilities:\nDesign and build systems with strong distributed systems expertise.\n"
    _, result, _ = _run_pathway(description, "Design and build systems with strong distributed systems expertise.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "responsibility_lead"


# ---------------------------------------------------------------------------
# Learning-opportunity content never gets a confident necessity.
# ---------------------------------------------------------------------------


def test_learning_opportunity_never_gets_a_confident_necessity_end_to_end():
    description = "What You'll Learn:\nFamiliarity with distributed systems.\n"
    _, result, _ = _run_pathway(description, "Familiarity with distributed systems.")
    assert not isinstance(result, DeclinedExtraction)
    assert result[0].necessity is None
    assert project_qualification(result[0]).unsafe_reason == "necessity_unknown"


# ---------------------------------------------------------------------------
# Company narrative is declined outright, even as a preamble before the
# document's own later real sections.
# ---------------------------------------------------------------------------


def test_company_narrative_preamble_declines_end_to_end():
    description = (
        "Our team has years of experience with distributed systems.\n\n"
        "Requirements:\nKnowledge of concurrency.\n"
    )
    _, narrative_result, doc_heading = _run_pathway(description, "Our team has years of experience with distributed systems.")
    assert doc_heading is True
    assert isinstance(narrative_result, DeclinedExtraction)
    assert narrative_result.reason == "narrative_cue"


# ---------------------------------------------------------------------------
# Applicability conditions are preserved but never silently scored.
# ---------------------------------------------------------------------------


def test_applicability_condition_preserved_and_routed_conservatively():
    description = "Requirements:\nExperience with distributed systems is expected, unless a manager approves an exception.\n"
    _, result, _ = _run_pathway(description, "Experience with distributed systems is expected, unless a manager approves an exception.")
    assert not isinstance(result, DeclinedExtraction)
    assert result[0].applicability_condition is not None
    assert result[0].necessity.value.upper() == "REQUIRED"
    projection = project_qualification(result[0])
    assert projection.job_requirement is None
    assert projection.unsafe_reason == "material_applicability_condition_not_representable_on_job_requirement"


# ---------------------------------------------------------------------------
# M11-G1's OR-list safety is intact end-to-end, under real section context.
# ---------------------------------------------------------------------------


def test_or_list_safety_intact_end_to_end():
    description = "Requirements:\nExperience with concurrency or distributed systems is required.\n"
    _, result, _ = _run_pathway(description, "Experience with concurrency or distributed systems is required.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "missing_contract"


# ---------------------------------------------------------------------------
# Named technology / education -- genuine qualifications outside the
# competency vocabulary -- are correctly declined, never fabricated into
# a competency tag.
# ---------------------------------------------------------------------------


def test_named_technology_outside_competency_scope_declines_end_to_end():
    description = "Requirements:\nExperience with Python is required.\n"
    _, result, _ = _run_pathway(description, "Experience with Python is required.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "no_competency_language"


def test_education_outside_competency_scope_declines_end_to_end():
    description = "Requirements:\nBachelor's degree in Computer Science is required.\n"
    _, result, _ = _run_pathway(description, "Bachelor's degree in Computer Science is required.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "no_competency_language"


# ---------------------------------------------------------------------------
# Disclosed finding: a genuine integration-interface mismatch between
# segmentation.py's own admission vocabulary and competency_extraction.py's
# own intent-gate vocabulary -- confirmed directly, not assumed.
# ---------------------------------------------------------------------------


def test_disclosed_integration_gap_strong_phrasing_outside_a_section_never_reaches_extractor():
    description = "Strong understanding of concurrency.\n"
    claim, result, doc_heading = _run_pathway(description, "Strong understanding of concurrency.")
    assert claim is None  # never became a Claim at all -- segmentation's own gate filtered it first
    assert doc_heading is False


# ---------------------------------------------------------------------------
# Disclosed finding: a genuine, pre-existing cross-tag alias overlap.
# ---------------------------------------------------------------------------


def test_disclosed_cross_tag_alias_overlap_distributed_architecture():
    description = "Minimum Qualifications:\nExperience with distributed architecture is required.\n"
    _, result, _ = _run_pathway(description, "Experience with distributed architecture is required.")
    assert not isinstance(result, DeclinedExtraction)
    tags = sorted(q.normalized_reference.competency_tag for q in result)
    assert tags == ["distributed-systems", "system-design"]


# ---------------------------------------------------------------------------
# The live parser's own pathway is untouched: this module is never
# imported by it, and v1 is never called by this harness at all.
# ---------------------------------------------------------------------------


def test_this_pathway_is_not_wired_into_the_live_parser():
    import gitscore.jobs.parsing.parser as parser_module
    import inspect

    source = inspect.getsource(parser_module)
    assert "extract_competency_qualifications" not in source
    assert "project_qualification" not in source
