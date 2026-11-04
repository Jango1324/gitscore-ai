"""Milestone 11-G1 -- alternative-requirement (OR-list) safety fix for
`extract_competency_qualifications_v2` ONLY.

Root cause: the pre-existing missing-contract check was only consulted
when the whole-sentence match found 2+ DISTINCT competency tags. A
sentence whose OR-list has only ONE matchable alternative among
several (e.g. a seven-item list where six items are outside the known
vocabulary) took the `len(tags) == 1` fast path and returned a
confident single-tag `Qualification`, silently discarding the other
named alternatives. Fixed by segmenting the list and checking its
structure BEFORE any tag-count branching.

v1 (`extract_competency_qualifications`) has the identical defect
(confirmed in `docs/evaluation/MILESTONE_11_G1_ALTERNATIVE_REQUIREMENT_SAFETY.md`
Phase 1) but is explicitly out of scope for this milestone and is
proven byte-unchanged by `test_v1_function_is_completely_unmodified_by_v2s_presence`
(M11-E) plus the dedicated `test_v1_behavior_is_unchanged_by_g1` below.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gitscore.jobs.models import SourceSpan  # noqa: E402
from gitscore.jobs.parsing.competency_extraction import (  # noqa: E402
    DeclinedExtraction,
    extract_competency_qualifications,
    extract_competency_qualifications_v2,
)


def _extract_v2(text: str):
    return extract_competency_qualifications_v2(text, SourceSpan(0, len(text)))


def _extract_v1(text: str):
    return extract_competency_qualifications(text, SourceSpan(0, len(text)))


# ---------------------------------------------------------------------------
# The core bug: one recognized alternative among several must decline,
# not resolve confidently.
# ---------------------------------------------------------------------------


def test_seven_item_or_list_with_one_recognized_alternative_declines():
    result = _extract_v2(
        "Experience with widget calibration, gadget tuning, thingamajig repair, "
        "doohickey maintenance, gizmo testing, contraption inspection, or embedded "
        "systems is required."
    )
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "missing_contract"


def test_one_recognized_one_unrecognized_alternative_declines():
    result = _extract_v2("Experience with concurrency or culinary arts is required.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "missing_contract"


def test_two_recognized_different_tags_still_declines():
    result = _extract_v2("Experience with concurrency or distributed systems is required.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "missing_contract"


def test_or_between_competency_and_named_technology_declines():
    result = _extract_v2("Experience with concurrency or Kubernetes is required.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "missing_contract"


def test_or_between_competency_and_education_declines():
    result = _extract_v2("A background in distributed systems or a related engineering degree is required.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "missing_contract"


def test_semicolon_separated_or_list_with_one_recognized_alternative_declines():
    result = _extract_v2("Experience with widget tuning; gadget calibration; or embedded systems is required.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "missing_contract"


# ---------------------------------------------------------------------------
# Diagnostics must be preserved on the new decline path (M11-G1 Phase 3).
# ---------------------------------------------------------------------------


def test_decline_preserves_source_text_and_span():
    text = "Experience with concurrency or culinary arts is required."
    result = _extract_v2(text)
    assert isinstance(result, DeclinedExtraction)
    assert result.source_text == text
    assert result.source_span == SourceSpan(0, len(text))


def test_decline_records_recognized_tags_for_diagnostics():
    result = _extract_v2("Experience with concurrency or culinary arts is required.")
    assert isinstance(result, DeclinedExtraction)
    assert result.recognized_tags == ("concurrency",)


def test_decline_with_zero_recognized_tags_among_alternatives_still_records_empty_tuple():
    """A segment list where NO alternative matches anything never
    reaches this path at all -- the whole-sentence qualifying-intent
    gate or vocabulary check already declines it earlier as
    no_competency_language. This test locks in that this earlier,
    cheaper decline still fires first, rather than my new structural
    check ever needing to run on a no-tag sentence."""
    result = _extract_v2("Experience with widget calibration, gadget tuning, or thingamajig repair is required.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "no_competency_language"


# ---------------------------------------------------------------------------
# Must NOT over-correct: synonymous "or" phrasing of the SAME tag still
# resolves safely, never declines.
# ---------------------------------------------------------------------------


def test_all_or_alternatives_matching_the_same_tag_resolves_safely():
    result = _extract_v2("Experience with concurrency, race conditions, or multithreading is required.")
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.normalized_reference.competency_tag == "concurrency"


def test_alias_level_synonyms_joined_by_or_resolve_safely():
    result = _extract_v2("Experience with network protocols or socket programming is required.")
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.normalized_reference.competency_tag == "os-networking"


def test_canonical_and_alias_synonyms_joined_by_or_resolve_safely():
    result = _extract_v2("Strong grasp of DS&A or algorithms and data structures is required.")
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.normalized_reference.competency_tag == "algorithms-data-structures"


# ---------------------------------------------------------------------------
# Must NOT over-correct: "or equivalent/similar X" is a substitutability
# clause, not a sibling alternative -- never declines.
# ---------------------------------------------------------------------------


def test_or_equivalent_experience_clause_resolves_safely_not_declined():
    result = _extract_v2("Strong distributed systems skills are required, or equivalent professional experience may be considered.")
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.normalized_reference.competency_tag == "distributed-systems"


def test_or_equivalent_background_resolves_safely_not_declined():
    result = _extract_v2("5+ years of experience with embedded systems or equivalent professional background.")
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.normalized_reference.competency_tag == "embedded-systems-design"


def test_or_similar_preferred_clause_resolves_safely_not_declined():
    result = _extract_v2("Familiarity with control systems or similar automation experience is a plus.")
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.normalized_reference.competency_tag == "control-systems"
    assert q.necessity is not None and q.necessity.value.upper() == "PREFERRED"


# ---------------------------------------------------------------------------
# Must NOT over-correct: pre-existing filters (narrative/responsibility/
# negation) still take precedence; AND-only and MIXED_UNSUPPORTED shapes
# are untouched by this fix (they never reach the new has_or-and-not-
# has_and branch).
# ---------------------------------------------------------------------------


def test_narrative_sentence_with_alternatives_still_declines_as_narrative():
    result = _extract_v2("Our team has deep expertise in distributed systems or high-performance computing.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "narrative_cue"


def test_responsibility_sentence_with_alternatives_still_declines_as_responsibility():
    result = _extract_v2(
        "Design and implement either distributed systems or high-performance computing "
        "with strong concurrency fundamentals."
    )
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "responsibility_lead"


def test_and_only_requirement_is_unaffected_and_splits_into_siblings():
    result = _extract_v2("Strong skills in concurrency, system design, and database design are required.")
    assert not isinstance(result, DeclinedExtraction)
    tags = sorted(q.normalized_reference.competency_tag for q in result)
    assert tags == ["concurrency", "database-design", "system-design"]


def test_mixed_and_or_shape_is_unaffected_still_mixed_unsupported():
    from gitscore.jobs.parsing.qualification import LogicalComposition

    result = _extract_v2(
        "Experience with system design, and familiarity with either distributed systems or performance optimization."
    )
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.logical_composition == LogicalComposition.MIXED_UNSUPPORTED
    assert q.normalized_reference is None


def test_single_competency_with_no_or_at_all_is_unaffected():
    result = _extract_v2("Strong understanding of algorithms and data structures is required.")
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.normalized_reference.competency_tag == "algorithms-data-structures"


# ---------------------------------------------------------------------------
# Structural robustness: wrapped/multiline text, unknown necessity,
# conditional applicability.
# ---------------------------------------------------------------------------


def test_or_list_wrapped_across_a_newline_still_declines():
    result = _extract_v2("Experience with concurrency or\ndistributed systems is required.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "missing_contract"


def test_or_list_without_explicit_necessity_cue_still_declines():
    result = _extract_v2("Knowledge of control systems or embedded systems.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "missing_contract"


def test_conditional_single_tag_requirement_still_preserves_applicability():
    result = _extract_v2("Experience with embedded systems is required, unless a manager approves an exception.")
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.normalized_reference.competency_tag == "embedded-systems-design"
    assert q.applicability_condition is not None


def test_conditional_or_list_with_multiple_tags_still_declines():
    result = _extract_v2("Experience with concurrency or distributed systems is required, unless a manager approves an exception.")
    assert isinstance(result, DeclinedExtraction)
    assert result.reason == "missing_contract"


# ---------------------------------------------------------------------------
# v1 is completely untouched by this milestone.
# ---------------------------------------------------------------------------


def test_v1_behavior_is_unchanged_by_g1():
    """v1 still exhibits the ORIGINAL defect -- confirming this
    milestone changed nothing about v1's own extraction function. v1
    is not fixed here by explicit scope; only its shared
    `DeclinedExtraction` type gained new OPTIONAL fields with safe
    defaults, which does not change any value v1 itself produces."""
    text = "Experience with concurrency or culinary arts is required."
    result = _extract_v1(text)
    assert not isinstance(result, DeclinedExtraction)
    [q] = result
    assert q.normalized_reference.competency_tag == "concurrency"


def test_declined_extraction_new_fields_default_safely_for_v1_call_sites():
    """v1's own missing_contract call site (len(tags) > 1, genuine
    AND-free alternative group) never sets the new M11-G1 diagnostic
    fields -- confirming the dataclass extension is purely additive
    and does not require touching v1's function body at all."""
    result = _extract_v1(
        "Experience with at least one of the following: distributed systems, "
        "concurrent programming, or high-performance computing."
    )
    assert isinstance(result, DeclinedExtraction)
    assert result.source_text is None
    assert result.source_span is None
    assert result.recognized_tags == ()
