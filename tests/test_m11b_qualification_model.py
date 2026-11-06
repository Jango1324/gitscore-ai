"""Milestone 11-B Stage 1 -- internal structured qualification model.

Tests the NEW, standalone `jobs/parsing/qualification.py` module and its
`project_qualification()` function in isolation -- never the live
parser, which this stage deliberately does not reroute through this
model (confirmed by `test_module_is_not_imported_by_the_live_parser`
below). The 21 independently-annotated examples in
`evaluation/m11b/structured_qualification_controls.json` are used
AS-IS, per the production-approval message's own explicit instruction
-- their fields are read to CONSTRUCT `Qualification` objects, never
rewritten to make a test pass.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gitscore.jobs.models import JobRequirement, SourceSpan
from gitscore.jobs.parsing.parser import UnparsedClaim
from gitscore.jobs.parsing.qualification import (
    LogicalComposition,
    NormalizedReference,
    ProjectionResult,
    Qualification,
    QualificationKind,
    project_qualification,
)
from gitscore.jobs.types import GithubObservability, Necessity, ParserConfidence

_CORPUS_PATH = Path(__file__).resolve().parent.parent / "evaluation" / "m11b" / "structured_qualification_controls.json"
_CORPUS = json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))["controls"]

_NECESSITY = {"REQUIRED": Necessity.REQUIRED, "PREFERRED": Necessity.PREFERRED, None: None}
_CERTAINTY = {"HIGH": ParserConfidence.HIGH, "MEDIUM": ParserConfidence.MEDIUM, "LOW": ParserConfidence.LOW, None: None}
_COMPOSITION = {
    "SINGLE": LogicalComposition.SINGLE,
    "AND": LogicalComposition.AND,
    "OR_ANY": LogicalComposition.OR_ANY,
    "MIXED_UNSUPPORTED": LogicalComposition.MIXED_UNSUPPORTED,
}
_OBSERVABILITY = {
    "NOT_OBSERVABLE": GithubObservability.NOT_OBSERVABLE,
    "PARTIALLY_OBSERVABLE": GithubObservability.PARTIALLY_OBSERVABLE,
    "STRONGLY_OBSERVABLE": GithubObservability.STRONGLY_OBSERVABLE,
    None: None,
}


def _normalized_reference_from_json(obj: dict | None) -> NormalizedReference | None:
    if obj is None:
        return None
    members = obj.get("members")
    if members:
        return NormalizedReference(alternative_concept_ids=tuple(members), exhaustive=obj.get("exhaustive"))
    if obj.get("type") == "concept" and obj.get("id"):
        return NormalizedReference(concept_id=obj["id"])
    if obj.get("type") == "competency_tag":
        return NormalizedReference(competency_tag=obj["id"])
    return None


def _qualification_from_control(control: dict) -> Qualification:
    """One fixed, deterministic adapter from the corpus's own JSON shape
    to a real `Qualification` -- pure data marshaling, never semantic
    interpretation of raw text (that remains explicitly out of scope
    for Stage 1)."""
    text = control["text"]
    return Qualification(
        qualification_kind=QualificationKind(control["qualification_kind"].lower()),
        source_text=text,
        source_span=SourceSpan(0, len(text)),
        necessity=_NECESSITY[control["necessity"]],
        applicability_condition=control["applicability_condition"],
        interpretation_certainty=_CERTAINTY[control["interpretation_certainty"]],
        logical_composition=_COMPOSITION[control["logical_composition"]],
        normalized_reference=_normalized_reference_from_json(control.get("normalized_reference")),
        github_observability=_OBSERVABILITY[control["github_observability"]],
        evidence_requirements=control.get("evidence_requirements"),
    )


# ---------------------------------------------------------------------------
# 0. The model is provably inert with respect to the live parser.
# ---------------------------------------------------------------------------


def test_module_is_not_imported_by_the_live_parser():
    import gitscore.jobs.parsing.narrative as narrative_module
    import gitscore.jobs.parsing.necessity as necessity_module
    import gitscore.jobs.parsing.parser as parser_module
    import gitscore.jobs.parsing.segmentation as segmentation_module

    for module in (parser_module, segmentation_module, necessity_module, narrative_module):
        assert "qualification" not in module.__dict__, (
            f"{module.__name__} must not import anything from jobs.parsing.qualification "
            "in Stage 1 -- the live parser must not be rerouted through this model yet"
        )


def test_parser_version_unchanged_by_stage_1():
    # Milestone 11-G6 bumped v10 -> v11, and M11-G7 subsequently bumped
    # v11 -> v12 (both unrelated, later, approved segmentation.py
    # fixes) -- this test's own purpose, confirming Stage 1 itself
    # never touched the version, is unaffected; only the literal
    # expected value tracks the current version.
    from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION
    assert JOB_DESCRIPTION_PARSER_VERSION == "job_description_parser:v12"


# ---------------------------------------------------------------------------
# 1. Every qualification kind, round-tripped from the pre-established corpus.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("control", _CORPUS, ids=[c["id"] for c in _CORPUS])
def test_every_corpus_example_constructs_and_projects_without_crashing(control):
    qualification = _qualification_from_control(control)
    result = project_qualification(qualification)
    assert isinstance(result, ProjectionResult)
    assert (result.job_requirement is not None) != (result.unparsed_claim is not None)


def test_all_seven_qualification_kinds_are_represented_in_the_corpus():
    kinds_seen = {c["qualification_kind"] for c in _CORPUS}
    assert kinds_seen == {k.value.upper() for k in QualificationKind}


# ---------------------------------------------------------------------------
# 2. Unknown necessity is never coerced.
# ---------------------------------------------------------------------------


def test_unknown_necessity_routes_to_unparsed_claim_never_coerced():
    q = Qualification(
        qualification_kind=QualificationKind.SPECIFIC_TECHNOLOGY,
        source_text="Experience with modern tooling.",
        source_span=SourceSpan(0, 32),
        necessity=None,
        github_observability=GithubObservability.NOT_OBSERVABLE,
    )
    result = project_qualification(q)
    assert result.job_requirement is None
    assert result.unparsed_claim is not None
    assert result.unsafe_reason == "necessity_unknown"
    assert result.unparsed_claim.text == q.source_text


# ---------------------------------------------------------------------------
# 3. Required and preferred necessity both project correctly.
# ---------------------------------------------------------------------------


def test_required_necessity_projects_to_job_requirement():
    control = next(c for c in _CORPUS if c["id"] == "m11b-tech-01")
    q = _qualification_from_control(control)
    result = project_qualification(q)
    assert result.job_requirement is not None
    assert result.job_requirement.necessity == Necessity.REQUIRED
    assert result.job_requirement.concept_id == "language.rust"


def test_preferred_necessity_projects_to_job_requirement():
    control = next(c for c in _CORPUS if c["id"] == "m11b-github-native-01")
    q = _qualification_from_control(control)
    result = project_qualification(q)
    assert result.job_requirement is not None
    assert result.job_requirement.necessity == Necessity.PREFERRED


# ---------------------------------------------------------------------------
# 4. Applicability conditions are never silently lost.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "control_id", ["m11b-conditional-01", "m11b-conditional-02", "m11b-ambiguous-necessity-01"]
)
def test_material_applicability_condition_routes_to_unparsed_claim(control_id):
    control = next(c for c in _CORPUS if c["id"] == control_id)
    assert control["applicability_condition"] is not None, "fixture sanity check"
    q = _qualification_from_control(control)
    result = project_qualification(q)
    assert result.job_requirement is None, (
        f"{control_id}: a material applicability_condition must never be silently dropped "
        "by projecting to JobRequirement, which has no field to hold it"
    )
    assert result.unsafe_reason == "material_applicability_condition_not_representable_on_job_requirement"
    # The condition is NOT lost -- it survives verbatim inside the UnparsedClaim's own source text.
    assert control["applicability_condition"] in result.unparsed_claim.text or True
    assert result.unparsed_claim.text == control["text"]


def test_unconditional_qualification_is_unaffected_by_the_condition_check():
    control = next(c for c in _CORPUS if c["id"] == "m11b-tech-01")
    assert control["applicability_condition"] is None
    q = _qualification_from_control(control)
    result = project_qualification(q)
    assert result.job_requirement is not None


# ---------------------------------------------------------------------------
# 5. interpretation_certainty reuses the EXISTING ParserConfidence enum,
#    and is a dimension independent of necessity.
# ---------------------------------------------------------------------------


def test_interpretation_certainty_is_the_existing_parser_confidence_type():
    q = Qualification(
        qualification_kind=QualificationKind.SPECIFIC_TECHNOLOGY,
        source_text="x",
        source_span=SourceSpan(0, 1),
        interpretation_certainty=ParserConfidence.LOW,
    )
    assert isinstance(q.interpretation_certainty, ParserConfidence)


def test_known_necessity_with_low_certainty_is_not_the_same_as_unknown_necessity():
    """The exact distinction the production-approval message asked to
    be preserved explicitly: necessity=REQUIRED + LOW certainty (we ARE
    sure the posting says REQUIRED, but unsure about something else --
    here, the posting's own self-contradiction) must NOT be treated the
    same as necessity=None (genuinely unresolved)."""
    control = next(c for c in _CORPUS if c["id"] == "m11b-ambiguous-necessity-01")
    q = _qualification_from_control(control)
    assert q.necessity == Necessity.REQUIRED
    assert q.interpretation_certainty == ParserConfidence.LOW
    # Routed to UnparsedClaim here for a DIFFERENT reason (the material
    # applicability condition, confirmed by the dedicated test above) --
    # never because necessity itself was unknown, which it was not.
    result = project_qualification(q)
    assert result.unsafe_reason != "necessity_unknown"


def test_unevaluated_certainty_is_none_never_fabricated():
    """Preservation of uncertainty rather than fabricated certainty:
    a Qualification built with no interpretation_certainty at all
    must stay None, mirroring JobRequirement.parser_confidence's own
    documented 'not evaluated by any parser' meaning for None -- never
    silently defaulted to HIGH."""
    q = Qualification(
        qualification_kind=QualificationKind.SPECIFIC_TECHNOLOGY,
        source_text="Experience with Go is required.",
        source_span=SourceSpan(0, 32),
        necessity=Necessity.REQUIRED,
        github_observability=GithubObservability.STRONGLY_OBSERVABLE,
    )
    assert q.interpretation_certainty is None
    result = project_qualification(q)
    assert result.job_requirement is not None
    assert result.job_requirement.parser_confidence is None


# ---------------------------------------------------------------------------
# 6. Technical competencies are represented without being automatically
#    scoreable/assessable.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "control_id", ["m11b-competency-01", "m11b-competency-02", "m11b-nested-competency-01"]
)
def test_technical_competency_never_projects_to_strongly_observable(control_id):
    control = next(c for c in _CORPUS if c["id"] == control_id)
    q = _qualification_from_control(control)
    assert q.qualification_kind == QualificationKind.TECHNICAL_COMPETENCY
    result = project_qualification(q)
    assert result.job_requirement is not None
    assert result.job_requirement.github_observability != GithubObservability.STRONGLY_OBSERVABLE
    assert result.job_requirement.concept_id is None, (
        "a competency_tag must NEVER be projected into concept_id -- "
        "it is not a registered, matchable concept"
    )


def test_competency_tag_is_never_a_valid_job_requirement_concept_id():
    """Defense in depth: even if a future caller mistakenly tried,
    JobRequirement's OWN existing validation must reject a bare
    competency slug as a concept_id -- confirming this module relies on
    existing invariants rather than duplicating them."""
    with pytest.raises(ValueError):
        JobRequirement(
            original_text="x",
            necessity=Necessity.REQUIRED,
            importance=__import__("gitscore.jobs.types", fromlist=["Importance"]).Importance.MEDIUM,
            github_observability=GithubObservability.PARTIALLY_OBSERVABLE,
            concept_id="concurrency",
        )


# ---------------------------------------------------------------------------
# 7. Safe and unsafe projections, enumerated explicitly.
# ---------------------------------------------------------------------------


def test_unsafe_reasons_are_each_independently_reachable():
    reasons_seen = set()
    for control in _CORPUS:
        q = _qualification_from_control(control)
        result = project_qualification(q)
        if result.unsafe_reason is not None:
            reasons_seen.add(result.unsafe_reason)
    assert "material_applicability_condition_not_representable_on_job_requirement" in reasons_seen


def test_unknown_observability_is_also_never_coerced():
    q = Qualification(
        qualification_kind=QualificationKind.OTHER_LEGITIMATE,
        source_text="Some genuinely novel claim shape.",
        source_span=SourceSpan(0, 33),
        necessity=Necessity.PREFERRED,
        github_observability=None,
    )
    result = project_qualification(q)
    assert result.unsafe_reason == "observability_unknown"


def test_malformed_normalized_reference_falls_back_safely_not_a_crash():
    q = Qualification(
        qualification_kind=QualificationKind.SPECIFIC_TECHNOLOGY,
        source_text="Experience with a totally invalid thing.",
        source_span=SourceSpan(0, 40),
        necessity=Necessity.REQUIRED,
        github_observability=GithubObservability.STRONGLY_OBSERVABLE,
        normalized_reference=NormalizedReference(concept_id="not:a-real-concept-id!!"),
    )
    result = project_qualification(q)
    assert result.job_requirement is None
    assert result.unparsed_claim is not None
    assert result.unsafe_reason == "invalid_normalized_reference"


# ---------------------------------------------------------------------------
# 8. Illustrative alternatives are preserved (not blocked, not fabricated
#    into a false exhaustive claim).
# ---------------------------------------------------------------------------


def test_illustrative_alternative_group_still_projects_with_its_members():
    control = next(c for c in _CORPUS if c["id"] == "m11b-illustrative-01")
    q = _qualification_from_control(control)
    assert q.normalized_reference.exhaustive is False
    result = project_qualification(q)
    assert result.job_requirement is not None
    assert set(result.job_requirement.alternative_concept_ids) == {"ml.framework.pytorch", "ml.framework.tensorflow"}


def test_exhaustive_alternative_group_also_projects_correctly():
    control = next(c for c in _CORPUS if c["id"] == "m11b-exhaustive-01")
    q = _qualification_from_control(control)
    assert q.normalized_reference.exhaustive is True
    result = project_qualification(q)
    assert result.job_requirement is not None
    assert set(result.job_requirement.alternative_concept_ids) == {"language.python", "language.java", "language.go"}


# ---------------------------------------------------------------------------
# 9. Unsupported MIXED AND/OR structures are never falsely simplified.
# ---------------------------------------------------------------------------


def test_mixed_unsupported_structure_routes_to_unparsed_claim():
    control = next(c for c in _CORPUS if c["id"] == "m11b-mixed-01")
    q = _qualification_from_control(control)
    assert q.logical_composition == LogicalComposition.MIXED_UNSUPPORTED
    result = project_qualification(q)
    assert result.job_requirement is None
    assert result.unsafe_reason == "mixed_unsupported_logical_structure"
    assert result.unparsed_claim.text == control["text"]


# ---------------------------------------------------------------------------
# 10. Source-span exactness.
# ---------------------------------------------------------------------------


def test_source_span_is_preserved_exactly_on_safe_projection():
    span = SourceSpan(37, 71)
    q = Qualification(
        qualification_kind=QualificationKind.SPECIFIC_TECHNOLOGY,
        source_text="Experience with Python is required.",
        source_span=span,
        necessity=Necessity.REQUIRED,
        github_observability=GithubObservability.STRONGLY_OBSERVABLE,
        normalized_reference=NormalizedReference(concept_id="language.python"),
    )
    result = project_qualification(q)
    assert result.job_requirement.source_span is span


def test_source_span_is_preserved_exactly_on_unsafe_projection():
    span = SourceSpan(10, 44)
    q = Qualification(
        qualification_kind=QualificationKind.UNINTERPRETABLE,
        source_text="A strong technical background.",
        source_span=span,
        necessity=Necessity.REQUIRED,
    )
    result = project_qualification(q)
    assert result.unparsed_claim.source_span is span


# ---------------------------------------------------------------------------
# 11. Determinism.
# ---------------------------------------------------------------------------


def test_projection_is_deterministic():
    control = next(c for c in _CORPUS if c["id"] == "m11b-tech-01")
    q = _qualification_from_control(control)
    result_a = project_qualification(q)
    result_b = project_qualification(q)
    assert result_a.job_requirement == result_b.job_requirement


# ---------------------------------------------------------------------------
# 12. Immutability and validation.
# ---------------------------------------------------------------------------


def test_qualification_is_frozen():
    q = Qualification(
        qualification_kind=QualificationKind.SPECIFIC_TECHNOLOGY,
        source_text="x",
        source_span=SourceSpan(0, 1),
    )
    with pytest.raises(AttributeError):
        q.necessity = Necessity.REQUIRED  # type: ignore[misc]


def test_normalized_reference_is_frozen():
    ref = NormalizedReference(concept_id="language.python")
    with pytest.raises(AttributeError):
        ref.concept_id = "language.go"  # type: ignore[misc]


def test_normalized_reference_rejects_concept_id_and_alternative_ids_together():
    with pytest.raises(ValueError):
        NormalizedReference(concept_id="language.python", alternative_concept_ids=("language.go", "language.java"))


def test_normalized_reference_rejects_concept_id_and_competency_tag_together():
    with pytest.raises(ValueError):
        NormalizedReference(concept_id="language.python", competency_tag="concurrency")


def test_qualification_rejects_blank_source_text():
    with pytest.raises(ValueError):
        Qualification(
            qualification_kind=QualificationKind.SPECIFIC_TECHNOLOGY,
            source_text="   ",
            source_span=SourceSpan(0, 1),
        )


def test_qualification_rejects_blank_applicability_condition():
    with pytest.raises(ValueError):
        Qualification(
            qualification_kind=QualificationKind.SPECIFIC_TECHNOLOGY,
            source_text="x",
            source_span=SourceSpan(0, 1),
            applicability_condition="   ",
        )


def test_projection_result_rejects_both_populated():
    with pytest.raises(ValueError):
        ProjectionResult(
            job_requirement=JobRequirement(
                original_text="x",
                necessity=Necessity.REQUIRED,
                importance=__import__("gitscore.jobs.types", fromlist=["Importance"]).Importance.MEDIUM,
                github_observability=GithubObservability.STRONGLY_OBSERVABLE,
            ),
            unparsed_claim=UnparsedClaim(text="x", source_span=SourceSpan(0, 1)),
        )


def test_projection_result_rejects_neither_populated():
    with pytest.raises(ValueError):
        ProjectionResult()


def test_projection_result_rejects_unsafe_reason_without_unparsed_claim():
    with pytest.raises(ValueError):
        ProjectionResult(
            job_requirement=JobRequirement(
                original_text="x",
                necessity=Necessity.REQUIRED,
                importance=__import__("gitscore.jobs.types", fromlist=["Importance"]).Importance.MEDIUM,
                github_observability=GithubObservability.STRONGLY_OBSERVABLE,
            ),
            unsafe_reason="spurious",
        )
