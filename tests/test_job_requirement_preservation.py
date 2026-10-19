"""Milestone 9A -- lossless job requirement parsing.

Focused gold examples for the M8E-identified high-severity bug: a
meaningful job-posting requirement bullet could silently produce ZERO
`JobRequirement` rows -- no row, no span, not even an `unresolved:<term>`
placeholder -- when its only technical content was not registered.

Each test below states its expected outcome FIRST (in the assertions),
independent of whatever the implementation happens to currently do --
these are gold examples, not a dump of observed output. Do not relax an
assertion here just to make it match a future refactor without first
re-confirming the underlying invariant it protects still holds.

Categories covered (Milestone 9A Phase 3):
  - recognized single requirement (regression control)
  - unknown single technical requirement
  - unknown technical OR-group
  - unknown technical AND-list (comma enumeration)
  - mixed known/unknown combination (regression control -- pre-9A path)
  - nontechnical professional-experience requirement (regression control)
  - ordinary prose that must NOT become a requirement (false-positive control)
  - real M8E examples (Vue/Angular, SPI/I2C/UART)
  - the sentence-initial-capitalization false positive this milestone's
    own design review caught and fixed ("Security certification such as
    OSCP or CISSP" must never fabricate `unresolved:security`)
"""
from __future__ import annotations

from gitscore.jobs.parsing.parser import parse_job_description
from gitscore.jobs.types import GithubObservability, Necessity, ParserConfidence


def _requirements(text: str):
    return parse_job_description(text, title="Test Role").requirements


# ---------------------------------------------------------------------------
# Regression controls -- behavior that existed before Milestone 9A and must
# be completely unaffected by it.
# ---------------------------------------------------------------------------

def test_recognized_single_requirement_unaffected():
    reqs = _requirements("Requirements:\n- Strong proficiency in Python\n")
    python_rows = [r for r in reqs if r.concept_id == "language.python"]
    assert len(python_rows) == 1
    assert python_rows[0].necessity == Necessity.REQUIRED
    assert python_rows[0].github_observability == GithubObservability.STRONGLY_OBSERVABLE


def test_mixed_known_and_unknown_combination_unaffected():
    """The ALREADY-WORKING sibling-confirmed comma-gate (pre-9A): a real
    concept (React) in the same comma list unlocks promotion of the
    OTHER unknown items to `unresolved:<term>` -- this is the one case
    that already worked and must not change at all.
    """
    reqs = _requirements("Requirements:\n- Experience with React, Vue, and SomeNewLibrary\n")
    concept_ids = {r.concept_id for r in reqs}
    assert "framework.react" in concept_ids
    assert "unresolved:vue" in concept_ids
    assert "unresolved:somenewlibrary" in concept_ids


def test_nontechnical_experience_requirement_unaffected():
    reqs = _requirements("Requirements:\n- 3+ years of professional experience\n")
    experience_rows = [r for r in reqs if r.category == "experience"]
    assert len(experience_rows) == 1
    assert experience_rows[0].concept_id is None
    assert experience_rows[0].github_observability == GithubObservability.NOT_OBSERVABLE


def test_degree_or_related_field_stays_non_technical_not_alternative():
    """Even though it contains "or", this must NEVER become a fabricated
    technical alternative group -- "Bachelor's"/"a related field" fail
    the specific-technology shape check (lowercase words / possessive).
    """
    reqs = _requirements("Requirements:\n- Bachelor's degree in Computer Science or a related field\n")
    assert not any(r.is_alternative_group for r in reqs)
    education_rows = [r for r in reqs if r.category == "education"]
    assert len(education_rows) == 1
    assert education_rows[0].concept_id is None


# ---------------------------------------------------------------------------
# The silent-drop fix itself.
# ---------------------------------------------------------------------------

def test_unknown_single_technical_requirement_is_preserved():
    """"Experience with dbt" -- previously ZERO rows at all (dbt has no
    comma/OR sibling to trigger any extraction path). Must now survive
    as an honest, non-fabricating placeholder, never SUPPORTED.
    """
    reqs = _requirements("Requirements:\n- Experience with dbt\n")
    assert len(reqs) == 1
    req = reqs[0]
    assert req.concept_id is None
    assert not req.is_alternative_group
    assert req.category == "unresolved_requirement"
    assert req.github_observability == GithubObservability.PARTIALLY_OBSERVABLE
    assert req.parser_confidence == ParserConfidence.LOW
    assert req.necessity == Necessity.REQUIRED


def test_unknown_technical_or_group_mints_unresolved_alternative():
    """M8E's own first known example: "Knowledge of Vue or Angular" --
    previously produced ZERO rows (any_confirmed was False and the
    per-segment unresolved ids were discarded). Must now produce ONE
    alternative-group requirement with both unresolved ids, never
    SUPPORTED by construction (no real concept registered).
    """
    reqs = _requirements("Preferred Qualifications:\n- Knowledge of Vue or Angular\n")
    assert len(reqs) == 1
    req = reqs[0]
    assert req.is_alternative_group
    assert req.alternative_concept_ids == ("unresolved:angular", "unresolved:vue")
    assert req.github_observability == GithubObservability.STRONGLY_OBSERVABLE
    assert req.necessity == Necessity.PREFERRED


def test_unknown_technical_and_list_mints_three_unresolved_rows():
    """M8E's own second known example: "SPI, I2C, and UART" -- previously
    ZERO rows for all three (the comma-gated unknown-term policy requires
    an already-confirmed sibling, and none of the three are registered).
    Must now produce THREE separate technical rows, one per item --
    matching the gold fixture's own encoded expectation exactly.
    """
    reqs = _requirements(
        "Requirements:\n"
        "- Familiarity with microcontroller peripherals such as SPI, I2C, and UART\n"
    )
    concept_ids = {r.concept_id for r in reqs if r.concept_id is not None}
    assert concept_ids == {"unresolved:spi", "unresolved:i2c", "unresolved:uart"}
    for req in reqs:
        assert req.github_observability == GithubObservability.STRONGLY_OBSERVABLE
        assert req.necessity == Necessity.REQUIRED


def test_unknown_or_group_with_no_technology_shape_falls_to_safety_net():
    """"control systems or state estimation" -- has "or", but NEITHER
    side is shaped like a specific named technology (both are lowercase
    descriptive phrases). Must NOT become a fabricated alternative group
    -- but must also not silently vanish; the generic placeholder catches
    it instead.
    """
    reqs = _requirements("Requirements:\n- Experience with control systems or state estimation\n")
    assert len(reqs) == 1
    req = reqs[0]
    assert not req.is_alternative_group
    assert req.concept_id is None
    assert req.category == "unresolved_requirement"


def test_sentence_initial_capitalization_does_not_fabricate_a_concept():
    """Regression test for a false positive this milestone's own design
    review caught before shipping: "Security" is capitalized ONLY
    because it starts the sentence, not because it is a technology name.
    Must never become `unresolved:security`.
    """
    reqs = _requirements("Requirements:\n- Security certification such as OSCP or CISSP\n")
    concept_ids = {r.concept_id for r in reqs} | {
        cid for r in reqs for cid in r.alternative_concept_ids
    }
    assert "unresolved:security" not in concept_ids
    assert len(reqs) == 1
    assert reqs[0].concept_id is None
    assert reqs[0].category == "unresolved_requirement"


# ---------------------------------------------------------------------------
# False-positive controls -- ordinary prose that must NOT become a
# requirement, with or without Milestone 9A's new fallback.
# ---------------------------------------------------------------------------

def test_ordinary_responsibility_prose_does_not_become_a_requirement():
    """No "or", no enumeration cue, no qualifying technical lead-in --
    must stay exactly as silent as before Milestone 9A (a known,
    documented, deliberately narrow scope limitation -- see
    docs/evaluation/MILESTONE_9A_REQUIREMENT_PRESERVATION.md).
    """
    reqs = _requirements(
        "Responsibilities:\n- Write clean, maintainable, and well-tested code\n"
    )
    assert not any("Write clean" in r.original_text for r in reqs)


def test_skip_section_prose_never_becomes_a_requirement():
    reqs = _requirements("Benefits:\n- We offer competitive salary and great snacks\n")
    assert reqs == ()


def test_soft_skill_short_phrase_does_not_trigger_the_lead_in_fallback():
    """"Strong communication" starts with "strong", one of the bare
    filler words `clean_list_fragment` strips for an ALREADY-CONFIRMED
    list item -- but must NOT, on its own, be treated as a qualifying
    technical lead-in for the new last-resort placeholder.
    """
    reqs = _requirements("Requirements:\n- Strong communication\n")
    assert not any(r.category == "unresolved_requirement" for r in reqs)
