"""Milestone 11-B Stage 2B -- Path A compatibility adapter tests.

Covers the 12 categories named by the Stage 2B approval message's own
"Phase 3 -- Evaluation controls" list, hardened to the corrected
acceptance bar (full `JobRequirement`/`UnparsedClaim` dataclass
equality, including `importance` and the raw `category` string --
see `qualification_adapter.py`'s own "Revision history" docstring for
why the first version fell short and how `AdaptedQualification` fixes
it). Wherever practical, fixtures are run through the REAL, unmodified
parser (`parse_job_description`/`parse_job_description_with_diagnostics`)
rather than hand-typed `JobRequirement`/`UnparsedClaim` objects, so
these tests exercise what the adapter actually sees in practice.

This module tests the ADAPTER's own correctness -- it does not re-test
`Qualification`/`project_qualification()` themselves (already covered
by `tests/test_m11b_qualification_model.py`).
"""
from __future__ import annotations

import pytest

from gitscore.api.serialization import _interpretation_status, serialize_requirement_match, serialize_unparsed_claim
from gitscore.jobs.models import JobRequirement, SourceSpan
from gitscore.jobs.parsing.parser import UnparsedClaim, parse_job_description, parse_job_description_with_diagnostics
from gitscore.jobs.parsing.qualification import QualificationKind, project_qualification
from gitscore.jobs.parsing.qualification_adapter import (
    UnsupportedAdapterCase,
    adapt_job_requirement,
    job_requirement_from_adapted,
    qualification_from_job_requirement,
    qualification_from_unparsed_claim,
)
from gitscore.jobs.types import GithubObservability, Importance, Necessity, ParserConfidence
from gitscore.matching.models import RequirementMatch
from gitscore.matching.types import MatchStatus

_CORE_PRESERVED_FIELDS = (
    "original_text",
    "necessity",
    "concept_id",
    "alternative_concept_ids",
    "github_observability",
    "parser_confidence",
    "source_span",
)


def _assert_core_fields_round_trip(original: JobRequirement, reconstructed: JobRequirement) -> None:
    for field in _CORE_PRESERVED_FIELDS:
        assert getattr(original, field) == getattr(reconstructed, field), (
            f"{field} did not round-trip: original={getattr(original, field)!r} "
            f"reconstructed={getattr(reconstructed, field)!r}"
        )


def _round_trip(requirement: JobRequirement) -> JobRequirement:
    """The FULL-FIDELITY round trip -- `adapt_job_requirement()` +
    `job_requirement_from_adapted()`, which patches `importance`/
    `category` back exactly, achieving full dataclass equality.
    """
    return job_requirement_from_adapted(adapt_job_requirement(requirement))


# ---------------------------------------------------------------------------
# 1. Existing required and preferred technical requirements.
# ---------------------------------------------------------------------------


def test_required_technical_requirement_round_trips_fully():
    profile = parse_job_description("Experience with Rust is required.")
    [requirement] = profile.requirements
    assert requirement.necessity == Necessity.REQUIRED
    reconstructed = _round_trip(requirement)
    assert reconstructed == requirement


def test_preferred_technical_requirement_round_trips_fully():
    profile = parse_job_description("Experience with Golang is a plus.")
    [requirement] = profile.requirements
    assert requirement.necessity == Necessity.PREFERRED
    reconstructed = _round_trip(requirement)
    assert reconstructed == requirement


# ---------------------------------------------------------------------------
# 2. Alternative technology groups.
# ---------------------------------------------------------------------------


def test_alternative_technology_group_round_trips_fully():
    profile = parse_job_description("Experience with Python or Go is required.")
    [requirement] = profile.requirements
    assert requirement.is_alternative_group
    reconstructed = _round_trip(requirement)
    assert reconstructed == requirement


# ---------------------------------------------------------------------------
# 3. Existing nontechnical requirements.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Strong written and verbal communication skills are required.",
        "Must be eligible to work in Canada.",
        "Experience mentoring other engineers is required.",
    ],
)
def test_nontechnical_requirement_round_trips_fully(text):
    profile = parse_job_description(text)
    assert profile.requirements, f"fixture produced no requirements: {text!r}"
    [requirement] = profile.requirements
    reconstructed = _round_trip(requirement)
    assert reconstructed == requirement
    qualification = qualification_from_job_requirement(requirement)
    assert qualification.qualification_kind == QualificationKind.NONTECHNICAL


# ---------------------------------------------------------------------------
# 4. Existing education and experience requirements.
# ---------------------------------------------------------------------------


def test_education_requirement_round_trips_fully():
    profile = parse_job_description("Bachelor's degree in Computer Science is required.")
    [requirement] = profile.requirements
    assert requirement.category == "education"
    reconstructed = _round_trip(requirement)
    assert reconstructed == requirement


def test_experience_requirement_round_trips_fully():
    profile = parse_job_description("5+ years of professional experience is required.")
    [requirement] = profile.requirements
    assert requirement.category == "experience"
    reconstructed = _round_trip(requirement)
    assert reconstructed == requirement


# ---------------------------------------------------------------------------
# 5. UnparsedClaim round trips.
# ---------------------------------------------------------------------------


def test_unparsed_claim_round_trips_exactly():
    parsed = parse_job_description_with_diagnostics(
        "Responsibilities:\nCollaborate with engineering and business teams to build user-focused solutions."
    )
    assert parsed.unparsed_claims, "fixture expected to produce at least one UnparsedClaim"
    claim = parsed.unparsed_claims[0]
    qualification = qualification_from_unparsed_claim(claim)
    result = project_qualification(qualification)
    assert result.job_requirement is None
    assert result.unparsed_claim == claim, "UnparsedClaim carries exactly 2 fields -- both must round-trip exactly"


# ---------------------------------------------------------------------------
# 6. Unknown or ambiguous diagnostic content.
# ---------------------------------------------------------------------------


def test_ambiguous_uninterpretable_claim_round_trips_as_unparsed():
    parsed = parse_job_description_with_diagnostics(
        "Responsibilities:\nA strong technical background and a passion for learning."
    )
    assert parsed.unparsed_claims, "fixture expected to produce at least one UnparsedClaim"
    claim = parsed.unparsed_claims[0]
    qualification = qualification_from_unparsed_claim(claim)
    assert qualification.qualification_kind == QualificationKind.UNINTERPRETABLE
    result = project_qualification(qualification)
    assert result.unparsed_claim == claim


# ---------------------------------------------------------------------------
# 7. Exact source spans (identity-level, pre- and post- round trip).
# ---------------------------------------------------------------------------


def test_source_span_is_exact_before_and_after_round_trip():
    description = "Requirements:\n- Experience with Rust is required.\n- Bachelor's degree in CS is required."
    profile = parse_job_description(description)
    for requirement in profile.requirements:
        span = requirement.source_span
        assert description[span.start : span.end] == requirement.original_text
        reconstructed = _round_trip(requirement)
        assert reconstructed == requirement
        recon_span = reconstructed.source_span
        assert recon_span is span or recon_span == span
        assert description[recon_span.start : recon_span.end] == reconstructed.original_text


# ---------------------------------------------------------------------------
# 8. Necessity and confidence preservation, across multiple confidence kinds.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected_confidence",
    [
        ("Experience with Rust is required.", ParserConfidence.HIGH),
        ("Bachelor's degree in Computer Science is required.", ParserConfidence.MEDIUM),
        ("Experience with control systems or state estimation is required.", ParserConfidence.LOW),
    ],
)
def test_necessity_and_confidence_preserved_across_confidence_kinds(text, expected_confidence):
    profile = parse_job_description(text)
    [requirement] = profile.requirements
    assert requirement.parser_confidence == expected_confidence
    reconstructed = _round_trip(requirement)
    assert reconstructed.necessity == requirement.necessity
    assert reconstructed.parser_confidence == requirement.parser_confidence


# ---------------------------------------------------------------------------
# 9. Requirement identity preservation.
# ---------------------------------------------------------------------------


def test_no_requirement_id_exists_identity_is_structural():
    """`JobRequirement` carries no `requirement_id` field at all (confirmed
    directly -- `jobs/models.py`'s own docstring: "No `requirement_id`:
    like `Evidence`, this is a pure value object"). "Identity" for this
    adapter now means the full, byte-for-byte `JobRequirement` itself --
    `_round_trip()` returning an object `==` to the original is a
    STRONGER guarantee than the dedup-key subset (`concept_id`/
    `alternative_concept_ids`/`necessity`) checked below, which is kept
    as an explicit, separate assertion since it is the field set
    `jobs/parsing/dedup.py`'s own policy actually keys on.
    """
    assert not hasattr(JobRequirement, "requirement_id")
    profile = parse_job_description("Experience with Rust is required.")
    [requirement] = profile.requirements
    reconstructed = _round_trip(requirement)
    assert reconstructed == requirement
    dedup_key_original = (requirement.concept_id, requirement.alternative_concept_ids, requirement.necessity)
    dedup_key_reconstructed = (reconstructed.concept_id, reconstructed.alternative_concept_ids, reconstructed.necessity)
    assert dedup_key_original == dedup_key_reconstructed


# ---------------------------------------------------------------------------
# 10. Serialization equality -- now exact, no documented exception needed.
# ---------------------------------------------------------------------------


def test_serialized_output_matches_exactly():
    profile = parse_job_description("Experience with Rust is required.")
    [requirement] = profile.requirements
    reconstructed = _round_trip(requirement)
    assert reconstructed == requirement

    match_original = RequirementMatch(requirement=requirement, status=MatchStatus.NOT_OBSERVED)
    match_reconstructed = RequirementMatch(requirement=reconstructed, status=MatchStatus.NOT_OBSERVED)
    out_original = serialize_requirement_match(match_original)
    out_reconstructed = serialize_requirement_match(match_reconstructed)

    assert out_original == out_reconstructed
    assert out_original.category == "language"
    assert out_reconstructed.category == "language"


def test_interpretation_status_is_preserved_for_the_two_existing_placeholder_categories():
    """Previously a confirmed, measured regression: the two existing
    placeholder categories (`"unresolved_requirement"`/
    `"alternative_requirement"`) both collapsed to `"other_legitimate"`
    after a round trip through the pre-correction adapter, changing
    `interpretation_status` from `"unparsed_placeholder"` to
    `"non_technical"`. `AdaptedQualification.legacy_category` now
    preserves the exact original string, so this must no longer occur.
    """
    profile = parse_job_description("Experience with control systems or state estimation is required.")
    [requirement] = profile.requirements
    assert requirement.category == "unresolved_requirement"
    reconstructed = _round_trip(requirement)
    assert reconstructed == requirement

    match_original = RequirementMatch(requirement=requirement, status=MatchStatus.NOT_ASSESSABLE)
    match_reconstructed = RequirementMatch(requirement=reconstructed, status=MatchStatus.NOT_ASSESSABLE)

    assert _interpretation_status(match_original) == "unparsed_placeholder"
    assert _interpretation_status(match_reconstructed) == "unparsed_placeholder"


def test_unparsed_claim_serialization_is_fully_preserved():
    parsed = parse_job_description_with_diagnostics(
        "Responsibilities:\nCollaborate with engineering and business teams to build user-focused solutions."
    )
    claim = parsed.unparsed_claims[0]
    qualification = qualification_from_unparsed_claim(claim)
    reconstructed_claim = project_qualification(qualification).unparsed_claim
    assert serialize_unparsed_claim(claim) == serialize_unparsed_claim(reconstructed_claim)


# ---------------------------------------------------------------------------
# 11. Unsupported / information-loss cases.
# ---------------------------------------------------------------------------


def test_missing_source_span_raises_unsupported_adapter_case_not_a_crash():
    requirement = JobRequirement(
        original_text="Experience with Rust is required.",
        necessity=Necessity.REQUIRED,
        importance=Importance.MEDIUM,
        github_observability=GithubObservability.STRONGLY_OBSERVABLE,
        concept_id="language.rust",
        source_span=None,
    )
    with pytest.raises(UnsupportedAdapterCase) as excinfo:
        adapt_job_requirement(requirement)
    assert excinfo.value.reason == "missing_source_span"


def test_importance_is_now_fully_preserved_when_it_is_not_medium():
    """Previously documented as a by-design gap -- now fixed by
    `AdaptedQualification.legacy_importance`. HIGH-importance
    requirements must round-trip exactly, never silently reconstructed
    as the Stage 1 MEDIUM placeholder.
    """
    profile = parse_job_description("Expert knowledge of Rust is required.")
    [requirement] = profile.requirements
    assert requirement.importance == Importance.HIGH, "fixture sanity check -- the HIGH-emphasis marker must fire"
    reconstructed = _round_trip(requirement)
    assert reconstructed.importance == Importance.HIGH
    assert reconstructed == requirement


def test_low_importance_from_preferred_necessity_is_now_fully_preserved():
    profile = parse_job_description("Familiarity with Golang is a plus.")
    [requirement] = profile.requirements
    assert requirement.importance == Importance.LOW
    reconstructed = _round_trip(requirement)
    assert reconstructed.importance == Importance.LOW
    assert reconstructed == requirement


def test_category_raw_string_is_now_fully_preserved_for_technical_requirements():
    profile = parse_job_description("Experience with PostgreSQL is required.")
    [requirement] = profile.requirements
    assert requirement.category == "database"
    reconstructed = _round_trip(requirement)
    assert reconstructed.category == "database"
    assert reconstructed == requirement


def test_qualification_kind_is_never_written_back_as_category():
    """`qualification_from_job_requirement`'s own `qualification_kind`
    derivation is used ONLY to shape the internal `Qualification` --
    it must never leak into the reconstructed `category`, which comes
    exclusively from `AdaptedQualification.legacy_category`.
    """
    profile = parse_job_description("Experience with PostgreSQL is required.")
    [requirement] = profile.requirements
    adapted = adapt_job_requirement(requirement)
    assert adapted.qualification.qualification_kind == QualificationKind.SPECIFIC_TECHNOLOGY
    assert adapted.legacy_category == "database"
    reconstructed = job_requirement_from_adapted(adapted)
    assert reconstructed.category == "database"
    assert reconstructed.category != adapted.qualification.qualification_kind.value


def test_unsafe_projection_raises_unsupported_adapter_case_rather_than_a_changed_object():
    """`job_requirement_from_adapted()` must never silently present a
    changed/unsafe object as a successful reconstruction -- if
    `project_qualification()` itself ever routed the inner
    `Qualification` to `UnparsedClaim` (not expected for any
    real-parser-sourced requirement, but not assumed impossible), this
    must raise, not return something different from the original.
    """
    from gitscore.jobs.parsing.qualification_adapter import AdaptedQualification
    from gitscore.jobs.parsing.qualification import LogicalComposition, Qualification

    unsafe_qualification = Qualification(
        qualification_kind=QualificationKind.UNINTERPRETABLE,
        source_text="Some claim.",
        source_span=SourceSpan(0, 11),
        necessity=None,  # forces an unsafe projection
    )
    adapted = AdaptedQualification(
        qualification=unsafe_qualification,
        legacy_importance=Importance.MEDIUM,
        legacy_category=None,
    )
    with pytest.raises(UnsupportedAdapterCase) as excinfo:
        job_requirement_from_adapted(adapted)
    assert excinfo.value.reason == "unsafe_projection"


# ---------------------------------------------------------------------------
# 12. Deterministic execution.
# ---------------------------------------------------------------------------


def test_adapter_and_projection_are_deterministic():
    profile = parse_job_description("Experience with Python or Go is required.")
    [requirement] = profile.requirements
    reconstructed_a = _round_trip(requirement)
    reconstructed_b = _round_trip(requirement)
    assert reconstructed_a == reconstructed_b == requirement


def test_adapter_is_not_imported_by_the_live_parser():
    import gitscore.jobs.parsing.narrative as narrative_module
    import gitscore.jobs.parsing.necessity as necessity_module
    import gitscore.jobs.parsing.parser as parser_module
    import gitscore.jobs.parsing.segmentation as segmentation_module

    for module in (parser_module, segmentation_module, necessity_module, narrative_module):
        assert "qualification_adapter" not in module.__dict__
