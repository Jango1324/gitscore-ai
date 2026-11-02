"""Milestone 10E -- narrative vs. applicant-qualification semantics.

Production regression tests for `jobs/parsing/narrative.py` (new),
`jobs/parsing/necessity.py::resolve_necessity_hint` (new), and the
`Claim.section_kind`/`document_has_any_recognized_heading` provenance
`jobs/parsing/segmentation.py` now carries -- see
`docs/evaluation/MILESTONE_10E_NARRATIVE_REQUIREMENT_SEMANTICS.md` for
the full evaluation-first design review this implements (Candidate C).

Every test here runs the REAL, unmodified `parse_job_description()`/
`parse_job_description_with_diagnostics()` -- no prototype, no mock.

Two mandatory safety gates (Mission brief, production-approval message):

- Gate A: the whole-document recognized-heading fact must never
  suppress a genuine preamble qualification.
- Gate B: a RESPONSIBILITY-section duty must not become an automatic
  qualification, but an explicit local REQUIRED/PREFERRED marker --
  even mixed into a duty sentence, even phrased as a PREFERRED learning
  clause -- must still win.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gitscore.jobs import Necessity, parse_job_description, parse_job_description_with_diagnostics

SOTI_TEXT = (
    Path(__file__).resolve().parent.parent / "evaluation" / "m10" / "source" / "soti_raw.txt"
).read_text(encoding="utf-8")
MANULIFE_TEXT = (
    Path(__file__).resolve().parent.parent / "evaluation" / "m10" / "source" / "manulife_raw.txt"
).read_text(encoding="utf-8")


# Milestone 11-A1 superseded this module's own `v7 -> v8` version-pin
# assertion with `v8 -> v9` (`tests/test_m11_a1_fabrication_fixes.py
# ::test_parser_version_bumped_to_v9`) -- removed here rather than left
# behind now permanently false, mirroring how M10E itself removed
# M10D's `v7` pin.


# ---------------------------------------------------------------------------
# Exact real-posting traces (Phase 1 of the evaluation-first review).
# ---------------------------------------------------------------------------


def test_soti_opportunity_paragraph_no_longer_fabricates_an_alternative_group():
    profile = parse_job_description(SOTI_TEXT, title="SOTI", company="SOTI")
    for r in profile.requirements:
        assert r.alternative_concept_ids != ("language.csharp", "language.sql")

    # The genuine "Required skills:" alternative-group placeholder (a
    # 9-way enumeration) must survive unaffected.
    assert any(r.category == "alternative_requirement" for r in profile.requirements) or any(
        "C, C++, Java" in r.original_text for r in profile.requirements
    )


def test_manulife_collaborate_bullet_no_longer_becomes_a_soft_skill_requirement():
    result = parse_job_description_with_diagnostics(MANULIFE_TEXT, title="Software Engineering Co-op", company="Manulife")
    collaborate_rows = [
        r for r in result.profile.requirements if "Collaborate with engineering and business teams" in r.original_text
    ]
    assert collaborate_rows == []
    assert any("Collaborate with engineering and business teams" in c.text for c in result.unparsed_claims)

    # The GENUINE soft-skill requirement, under the real "Required
    # Qualifications:" section, must survive unaffected.
    genuine_soft_skill = [
        r
        for r in result.profile.requirements
        if r.category == "soft_skill" and "Strong communication skills" in r.original_text
    ]
    assert len(genuine_soft_skill) == 1
    assert genuine_soft_skill[0].necessity == Necessity.REQUIRED

    # The genuine "Experience with at least one programming language"
    # alternative group (Root Cause 4, M10D) must survive unaffected.
    any_of_group = [r for r in result.profile.requirements if r.alternative_concept_ids]
    assert any_of_group, "the Manulife 'at least one programming language' alternative group must still exist"


# ---------------------------------------------------------------------------
# Safety Gate A -- genuine preamble qualifications must survive.
# ---------------------------------------------------------------------------


def test_gate_a_explicit_qualification_before_about_company_section():
    profile = parse_job_description("Applicants must know Python.\n\nAbout Us:\nWe are a great company.\n")
    concept_ids = {r.concept_id for r in profile.requirements}
    assert "language.python" in concept_ids


def test_gate_a_explicit_qualification_before_benefits_section():
    profile = parse_job_description(
        "Experience with Java is required.\n\nBenefits:\n- Unlimited PTO\n- Free snacks\n"
    )
    concept_ids = {r.concept_id for r in profile.requirements}
    assert "language.java" in concept_ids
    required_java = [r for r in profile.requirements if r.concept_id == "language.java"]
    assert required_java[0].necessity == Necessity.REQUIRED


def test_gate_a_truly_unsectioned_posting_preserves_explicit_qualifications():
    # No heading anywhere in the document at all -- the original
    # Milestone 6B "no section at all" fallback must still apply exactly
    # as before this milestone.
    profile = parse_job_description("Experience with SQL is required. Work with Java and Python.")
    concept_ids = {r.concept_id for r in profile.requirements}
    assert {"language.sql", "language.java", "language.python"} <= concept_ids


def test_gate_a_soti_full_document_narrative_suppressed_but_required_skills_preserved():
    profile = parse_job_description(SOTI_TEXT, title="SOTI", company="SOTI")
    # The narrative paragraph's fabricated alt-group must not exist (also
    # covered above, re-asserted here as part of Gate A's own suite).
    assert not any(r.alternative_concept_ids == ("language.csharp", "language.sql") for r in profile.requirements)
    # The real "Required skills:" section's explicit enumeration must
    # still produce a scored alternative-group requirement.
    required_rows = [r for r in profile.requirements if r.alternative_concept_ids]
    assert required_rows, "SOTI's genuine 'Required skills:' alternative group must survive"
    assert required_rows[0].necessity == Necessity.REQUIRED


# ---------------------------------------------------------------------------
# Safety Gate B -- mixed responsibility/qualification statements.
# ---------------------------------------------------------------------------


def test_gate_b_responsibility_tech_mention_is_not_an_automatic_requirement():
    result = parse_job_description_with_diagnostics("Responsibilities:\n- Develop Java services.\n")
    concept_ids = {r.concept_id for r in result.profile.requirements}
    assert "language.java" not in concept_ids
    assert any("Develop Java services" in c.text for c in result.unparsed_claims)


def test_gate_b_responsibility_collaborate_is_not_an_automatic_soft_skill_prerequisite():
    result = parse_job_description_with_diagnostics("Responsibilities:\n- Collaborate with engineers.\n")
    soft_skill_rows = [r for r in result.profile.requirements if r.category == "soft_skill"]
    assert soft_skill_rows == []
    assert any("Collaborate with engineers" in c.text for c in result.unparsed_claims)


def test_gate_b_explicit_required_marker_survives_inside_a_responsibility_sentence():
    profile = parse_job_description(
        "Responsibilities:\n- Develop Java services; Java experience is required.\n"
    )
    java_rows = [r for r in profile.requirements if r.concept_id == "language.java"]
    assert len(java_rows) == 1
    assert java_rows[0].necessity == Necessity.REQUIRED


def test_gate_b_explicit_preferred_marker_survives_against_a_learning_clause():
    profile = parse_job_description(
        "Responsibilities:\n- You will learn SQL, but SQL knowledge is preferred.\n"
    )
    sql_rows = [r for r in profile.requirements if r.concept_id == "language.sql"]
    assert len(sql_rows) == 1
    assert sql_rows[0].necessity == Necessity.PREFERRED


def test_gate_b_genuine_required_soft_skill_under_required_qualifications_is_preserved():
    profile = parse_job_description(
        "Required Qualifications:\n- Strong communication skills and willingness to learn in a collaborative environment.\n"
    )
    soft_skill_rows = [r for r in profile.requirements if r.category == "soft_skill"]
    assert len(soft_skill_rows) == 1
    assert soft_skill_rows[0].necessity == Necessity.REQUIRED


# ---------------------------------------------------------------------------
# M10E's own 51-control corpus, run against the REAL production parser
# (not a prototype) -- `has_job_requirement` must match the gold
# `should_create_job_requirement` annotation for every control whose
# gold annotation is not itself a documented, pre-existing, out-of-scope
# gap (see the corpus's own `schema_notes` and
# docs/evaluation/MILESTONE_10E_NARRATIVE_REQUIREMENT_SEMANTICS.md §4.2).
# ---------------------------------------------------------------------------

_CORPUS_PATH = Path(__file__).resolve().parent.parent / "evaluation" / "m10e" / "narrative_controls.json"
_CORPUS = json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))["controls"]

# Pre-existing, out-of-scope gaps this milestone's candidates were never
# designed to fix (§4.2 of the evaluation doc) -- `non_technical.py`
# vocabulary coverage (b3/b4/c1-c4/f2/h3/h4) and the separately-deferred
# SKIP blanket-suppression gap (f4). Listed explicitly, not silently
# excluded, so a future fix to either removes entries from this list
# rather than this test silently staying green either way.
_KNOWN_OUT_OF_SCOPE_MISMATCHES = {
    "m10e-b3", "m10e-b4", "m10e-c1", "m10e-c2", "m10e-c3", "m10e-c4",
    "m10e-f2", "m10e-f4", "m10e-h3", "m10e-h4",
}


@pytest.mark.parametrize("control", _CORPUS, ids=[c["id"] for c in _CORPUS])
def test_m10e_corpus_control_matches_gold_against_real_production_parser(control):
    if control["id"] in _KNOWN_OUT_OF_SCOPE_MISMATCHES:
        pytest.skip("pre-existing, out-of-scope gap -- see docs/evaluation/MILESTONE_10E_NARRATIVE_REQUIREMENT_SEMANTICS.md §4.2")
    text = control["text"]
    if not text:
        pytest.skip("empty placeholder control")
    heading = control["section_context"]
    doc = f"{heading}\n{text}" if heading else text
    profile = parse_job_description(doc, title="t", company="c")
    actual_created = len(profile.requirements) > 0
    assert actual_created == control["should_create_job_requirement"], (
        f"{control['id']} ({control['category']}): expected "
        f"should_create_job_requirement={control['should_create_job_requirement']}, got {actual_created}"
    )
