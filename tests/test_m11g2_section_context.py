"""Milestone 11-G2 -- section-aware qualification/necessity inference,
opt-in, for `extract_competency_qualifications_v2` ONLY.

Root cause: this module's necessity inference has always been purely
local (`infer_necessity(text, None)`), even though the live parser's
own `segmentation.py` already computes a section-origin signal
(`Claim.section_kind`) and `necessity.py::resolve_necessity_hint`
already implements the full, already-tested policy for using it. This
milestone reuses that existing machinery (Phase 3's "Option A") rather
than building a parallel, independently-maintained duplicate.

Opt-in and fully backward-compatible: `has_section_context` defaults to
`False`, in which case necessity resolution is byte-identical to the
pre-M11-G2 form -- verified below.
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
from gitscore.jobs.parsing.segmentation import (  # noqa: E402
    document_has_any_recognized_heading,
    segment_description,
)


def _extract(text: str, **kwargs):
    return extract_competency_qualifications_v2(text, SourceSpan(0, len(text)), **kwargs)


# ---------------------------------------------------------------------------
# Backward compatibility: legacy call path is byte-identical.
# ---------------------------------------------------------------------------


def test_legacy_call_with_no_section_kwargs_is_unaffected():
    text = "Experience with distributed systems."
    result = _extract(text)
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.necessity is None


def test_has_section_context_false_explicitly_matches_legacy_behavior():
    text = "Experience with distributed systems."
    legacy = _extract(text)
    explicit = _extract(text, section_kind="REQUIRED", document_has_recognized_heading=True, has_section_context=False)
    assert legacy[0].necessity == explicit[0].necessity is None


# ---------------------------------------------------------------------------
# REQUIRED / PREFERRED sections without a local marker now get the
# correct default necessity.
# ---------------------------------------------------------------------------


def test_required_section_with_no_local_marker_resolves_required():
    result = _extract(
        "Experience with distributed systems.",
        section_kind="REQUIRED", document_has_recognized_heading=True, has_section_context=True,
    )
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.normalized_reference.competency_tag == "distributed-systems"
    assert q.necessity is not None and q.necessity.value.upper() == "REQUIRED"


def test_preferred_section_with_no_local_marker_resolves_preferred():
    result = _extract(
        "Knowledge of concurrency.",
        section_kind="PREFERRED", document_has_recognized_heading=True, has_section_context=True,
    )
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.necessity is not None and q.necessity.value.upper() == "PREFERRED"


# ---------------------------------------------------------------------------
# RESPONSIBILITY/LEARNING/UNKNOWN sections, and a preamble before the
# document's later real sections, correctly stay UNKNOWN (necessity=None)
# without a local marker -- never silently defaulted.
# ---------------------------------------------------------------------------


def test_responsibility_section_without_local_marker_stays_unknown():
    result = _extract(
        "Strong ownership of distributed systems reliability.",
        section_kind="RESPONSIBILITY", document_has_recognized_heading=True, has_section_context=True,
    )
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.normalized_reference.competency_tag == "distributed-systems"
    assert q.necessity is None


def test_learning_section_without_local_marker_stays_unknown():
    result = _extract(
        "Strong exposure to distributed systems.",
        section_kind="LEARNING", document_has_recognized_heading=True, has_section_context=True,
    )
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.necessity is None


def test_unknown_heading_without_local_marker_stays_unknown():
    result = _extract(
        "Experience with distributed systems.",
        section_kind="UNKNOWN", document_has_recognized_heading=True, has_section_context=True,
    )
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.necessity is None


def test_preamble_before_later_real_sections_stays_unknown():
    result = _extract(
        "Strong background in distributed systems.",
        section_kind=None, document_has_recognized_heading=True, has_section_context=True,
    )
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.necessity is None


# ---------------------------------------------------------------------------
# Genuinely unsectioned whole document preserves Milestone 6B's own
# "no section at all -> default REQUIRED" policy.
# ---------------------------------------------------------------------------


def test_genuinely_unsectioned_document_still_defaults_required():
    result = _extract(
        "Strong understanding of concurrency.",
        section_kind=None, document_has_recognized_heading=False, has_section_context=True,
    )
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.necessity is not None and q.necessity.value.upper() == "REQUIRED"


# ---------------------------------------------------------------------------
# An explicit local marker always wins, preserving genuine
# qualifications under ANY section, including unconventional ones.
# ---------------------------------------------------------------------------


def test_explicit_local_marker_preserved_under_unknown_heading():
    result = _extract(
        "Distributed systems experience is required.",
        section_kind="UNKNOWN", document_has_recognized_heading=True, has_section_context=True,
    )
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.necessity is not None and q.necessity.value.upper() == "REQUIRED"


def test_explicit_local_marker_preserved_under_learning_heading():
    result = _extract(
        "Embedded systems experience is required.",
        section_kind="LEARNING", document_has_recognized_heading=True, has_section_context=True,
    )
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.necessity is not None and q.necessity.value.upper() == "REQUIRED"


def test_local_marker_overrides_section_default_in_either_direction():
    preferred_in_required_section = _extract(
        "Distributed systems experience is preferred.",
        section_kind="REQUIRED", document_has_recognized_heading=True, has_section_context=True,
    )
    required_in_preferred_section = _extract(
        "Concurrency experience is required.",
        section_kind="PREFERRED", document_has_recognized_heading=True, has_section_context=True,
    )
    assert preferred_in_required_section[0].necessity.value.upper() == "PREFERRED"
    assert required_in_preferred_section[0].necessity.value.upper() == "REQUIRED"


# ---------------------------------------------------------------------------
# G1's OR-list safety fix is completely unaffected by section context.
# ---------------------------------------------------------------------------


def test_or_list_safety_still_declines_under_required_section():
    result = _extract(
        "Experience with concurrency or distributed systems is required.",
        section_kind="REQUIRED", document_has_recognized_heading=True, has_section_context=True,
    )
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "missing_contract"


def test_synonymous_or_still_resolves_safely_with_section_context():
    result = _extract(
        "Strong grasp of concurrency, race conditions, or multithreading is expected.",
        section_kind="RESPONSIBILITY", document_has_recognized_heading=True, has_section_context=True,
    )
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.normalized_reference.competency_tag == "concurrency"
    assert q.necessity is None


# ---------------------------------------------------------------------------
# Negation/narrative/responsibility-lead rejection is unaffected by
# section context -- those checks run before necessity is ever computed.
# ---------------------------------------------------------------------------


def test_negation_still_declines_regardless_of_section_context():
    result = _extract(
        "No prior experience with embedded systems is necessary.",
        section_kind="REQUIRED", document_has_recognized_heading=True, has_section_context=True,
    )
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "negation"


# ---------------------------------------------------------------------------
# Applicability conditions are preserved identically with section context.
# ---------------------------------------------------------------------------


def test_applicability_condition_preserved_with_section_context():
    result = _extract(
        "Experience with distributed systems is expected, unless a manager approves an exception.",
        section_kind="REQUIRED", document_has_recognized_heading=True, has_section_context=True,
    )
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.applicability_condition is not None
    assert q.necessity is not None and q.necessity.value.upper() == "REQUIRED"


# ---------------------------------------------------------------------------
# End-to-end plumbing: a REAL mini-posting through segment_description()
# produces correct, independent necessity per claim.
# ---------------------------------------------------------------------------


def test_end_to_end_required_and_preferred_transition_via_real_segmentation():
    description = (
        "Requirements:\nExperience with distributed systems.\n\n"
        "Preferred Qualifications:\nKnowledge of concurrency.\n"
    )
    claims = segment_description(description)
    doc_heading = document_has_any_recognized_heading(description)
    by_text = {c.text: c for c in claims}

    required_claim = by_text["Experience with distributed systems."]
    preferred_claim = by_text["Knowledge of concurrency."]

    required_result = extract_competency_qualifications_v2(
        required_claim.text, SourceSpan(required_claim.start, required_claim.end),
        section_kind=required_claim.section_kind, document_has_recognized_heading=doc_heading,
        has_section_context=True,
    )
    preferred_result = extract_competency_qualifications_v2(
        preferred_claim.text, SourceSpan(preferred_claim.start, preferred_claim.end),
        section_kind=preferred_claim.section_kind, document_has_recognized_heading=doc_heading,
        has_section_context=True,
    )

    assert required_result[0].necessity.value.upper() == "REQUIRED"
    assert preferred_result[0].necessity.value.upper() == "PREFERRED"


def test_end_to_end_mixed_technical_and_education_bullet_under_same_section():
    description = (
        "Requirements:\n- Strong experience with distributed systems.\n"
        "- Bachelor's degree in Computer Science.\n"
    )
    claims = segment_description(description)
    doc_heading = document_has_any_recognized_heading(description)
    by_text = {c.text: c for c in claims}

    technical = by_text["Strong experience with distributed systems."]
    result = extract_competency_qualifications_v2(
        technical.text, SourceSpan(technical.start, technical.end),
        section_kind=technical.section_kind, document_has_recognized_heading=doc_heading,
        has_section_context=True,
    )
    assert result[0].necessity.value.upper() == "REQUIRED"

    education = by_text["Bachelor's degree in Computer Science."]
    education_result = extract_competency_qualifications_v2(
        education.text, SourceSpan(education.start, education.end),
        section_kind=education.section_kind, document_has_recognized_heading=doc_heading,
        has_section_context=True,
    )
    assert isinstance(education_result, DeclinedExtraction)
    assert education_result.reason == "no_competency_language"


# ---------------------------------------------------------------------------
# v1 is completely untouched by this milestone.
# ---------------------------------------------------------------------------


def test_v1_has_no_section_kwargs_at_all():
    from gitscore.jobs.parsing.competency_extraction import extract_competency_qualifications
    import inspect

    sig = inspect.signature(extract_competency_qualifications)
    assert "section_kind" not in sig.parameters
    assert "has_section_context" not in sig.parameters
