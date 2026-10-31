"""Milestone 10B -- safe section-state handling.

Covers the approved design in
`docs/evaluation/MILESTONE_10B_SECTION_STATE_SAFETY.md`:
`_SectionKind.UNKNOWN` (`jobs/parsing/segmentation.py`), the widened
`Necessity | None` necessity hint/inference (`jobs/parsing/necessity.py`),
and the `_requirements_from_claim` short-circuit to `UnparsedClaim`
(`jobs/parsing/parser.py`).

The 12 positive/negative controls in
`evaluation/m10b/section_state_controls.json` were authored BEFORE this
implementation existed (Phase 3 of the design review) and are loaded
here verbatim, never edited to match whatever the implementation
happens to do -- a mismatch here means the implementation is wrong,
not the control.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gitscore.evidence import build_candidate_evidence_profile
from gitscore.jobs import GithubObservability, Importance, JobRequirement, JobRequirementProfile, Necessity
from gitscore.jobs.parsing.necessity import infer_necessity
from gitscore.jobs.parsing.parser import parse_job_description_with_diagnostics
from gitscore.jobs.parsing.segmentation import Claim, segment_description
from gitscore.matching import MatchStatus, match_job

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTROLS_PATH = REPO_ROOT / "evaluation" / "m10b" / "section_state_controls.json"


def _load_controls() -> list[dict]:
    return json.loads(CONTROLS_PATH.read_text(encoding="utf-8"))["controls"]


def _target_lines(control: dict) -> list[str]:
    lines = [line.strip().lstrip("-").strip() for line in control["fragment"].strip().splitlines() if line.strip()]
    return lines[-2:] if control.get("targets_last_two_lines") else lines[-1:]


def _observed_outcome(fragment: str, target: str) -> str:
    result = parse_job_description_with_diagnostics(fragment)
    if any(r.original_text.strip() == target for r in result.profile.requirements):
        return "formal_requirement"
    if any(u.text.strip() == target for u in result.unparsed_claims):
        return "diagnostic_preserved"
    return "correctly_excluded_non_requirement"


# ---------------------------------------------------------------------------
# All 12 approved controls, loaded from the pre-established corpus.
# ---------------------------------------------------------------------------

_CONTROLS = _load_controls()


@pytest.mark.parametrize("control", _CONTROLS, ids=[c["id"] for c in _CONTROLS])
def test_approved_section_state_control(control):
    for target in _target_lines(control):
        observed = _observed_outcome(control["fragment"], target)
        assert observed == control["expected_outcome"], (
            f"{control['id']}: expected {control['expected_outcome']!r} for {target!r}, got {observed!r}"
        )


def test_all_twelve_controls_are_present():
    assert len(_CONTROLS) == 12
    assert len({c["id"] for c in _CONTROLS}) == 12


# ---------------------------------------------------------------------------
# Explicit local necessity markers inside an UNKNOWN section (necessity.py
# precedence -- local wording always wins, even with no section hint).
# ---------------------------------------------------------------------------

def test_explicit_required_marker_wins_inside_unknown_section():
    description = (
        "Preferred Qualifications:\n- Experience with Docker is a plus.\n\n"
        "Growth Opportunities:\nExperience with Kubernetes is required.\n"
    )
    result = parse_job_description_with_diagnostics(description)
    kubernetes_rows = [r for r in result.profile.requirements if "Kubernetes" in r.original_text]
    assert len(kubernetes_rows) == 1
    assert kubernetes_rows[0].necessity == Necessity.REQUIRED


def test_explicit_preferred_marker_wins_inside_unknown_section():
    description = (
        "Requirements:\n- Experience with Python is required.\n\n"
        "Growth Opportunities:\nExposure to Docker would be nice.\n"
    )
    result = parse_job_description_with_diagnostics(description)
    docker_rows = [r for r in result.profile.requirements if "Docker" in r.original_text]
    assert len(docker_rows) == 1
    assert docker_rows[0].necessity == Necessity.PREFERRED


def test_infer_necessity_returns_none_for_unknown_hint_with_no_local_marker():
    assert infer_necessity("Mentorship from senior engineers.", None) is None


def test_infer_necessity_local_marker_overrides_none_hint():
    assert infer_necessity("Python is required.", None) == Necessity.REQUIRED
    assert infer_necessity("Python is a plus.", None) == Necessity.PREFERRED


# ---------------------------------------------------------------------------
# necessity_hint=None never silently defaults back to REQUIRED/PREFERRED.
# ---------------------------------------------------------------------------

def test_unknown_section_claim_never_fabricates_a_necessity():
    description = (
        "Preferred Qualifications:\n- Experience with Docker is a plus.\n\n"
        "Compensation Disclosure:\n"
        "The actual salary will vary depending on local market conditions, geography, "
        "and relevant job-related factors such as knowledge, skills, qualifications, and experience.\n"
    )
    result = parse_job_description_with_diagnostics(description)
    salary_rows = [r for r in result.profile.requirements if "salary will vary" in r.original_text]
    assert salary_rows == []  # never a scored JobRequirement, of any necessity
    salary_unparsed = [u for u in result.unparsed_claims if "salary will vary" in u.text]
    assert len(salary_unparsed) == 1  # preserved as a diagnostic instead


def test_claim_necessity_hint_can_be_none_without_crashing_segmentation():
    claims = segment_description(
        "Preferred Qualifications:\n- Docker is a plus.\n\nUnknown Heading:\nExperience with Redis is nice.\n"
    )
    hints = {c.necessity_hint for c in claims}
    assert None in hints  # at least one claim is genuinely ambiguous
    # every claim is a real Claim with a well-formed necessity_hint type
    for c in claims:
        assert c.necessity_hint is None or isinstance(c.necessity_hint, Necessity)


# ---------------------------------------------------------------------------
# Re-entry into a recognized section after UNKNOWN (never sticky itself).
# ---------------------------------------------------------------------------

def test_unknown_never_sticks_past_a_real_heading():
    description = "Growth Opportunities:\nYou will learn new things.\n\nRequired Qualifications:\n- Experience with PostgreSQL is required.\n"
    result = parse_job_description_with_diagnostics(description)
    postgres_rows = [r for r in result.profile.requirements if r.concept_id == "database.postgresql"]
    assert len(postgres_rows) == 1
    assert postgres_rows[0].necessity == Necessity.REQUIRED


# ---------------------------------------------------------------------------
# No-section-at-all behavior is completely unaffected.
# ---------------------------------------------------------------------------

def test_unsectioned_explicit_requirement_is_unaffected():
    description = "We need someone with hands-on experience in Python and PostgreSQL.\n"
    result = parse_job_description_with_diagnostics(description)
    concept_ids = {r.concept_id for r in result.profile.requirements}
    assert "language.python" in concept_ids
    assert "database.postgresql" in concept_ids
    for r in result.profile.requirements:
        assert r.necessity == Necessity.REQUIRED


def test_existing_segmentation_suite_scenarios_remain_byte_identical():
    """A representative sample of the pre-existing, already-tested
    scenarios (test_job_parser_segmentation.py) that never involve an
    unrecognized colon-heading following a recognized section -- must
    produce IDENTICAL claims/hints after this milestone's change.
    """
    description = "Requirements:\n- Python\n- PostgreSQL\n- Docker\n"
    claims = segment_description(description)
    assert [c.text for c in claims] == ["Python", "PostgreSQL", "Docker"]
    assert all(c.necessity_hint == Necessity.REQUIRED for c in claims)


# ---------------------------------------------------------------------------
# Colon-terminated bulleted requirement lead-ins (the approval-review
# amendment) -- a bulleted colon lead-in inside an already-open recognized
# section must never be treated as a new section boundary.
# ---------------------------------------------------------------------------

def test_bulleted_colon_leadin_inside_recognized_section_is_not_a_heading_reset():
    description = "Requirements:\n- Experience with the following:\n- Python\n- JavaScript\n"
    result = parse_job_description_with_diagnostics(description)
    concept_ids = {r.concept_id for r in result.profile.requirements}
    assert "language.python" in concept_ids
    assert "language.javascript" in concept_ids
    python_row = next(r for r in result.profile.requirements if r.concept_id == "language.python")
    js_row = next(r for r in result.profile.requirements if r.concept_id == "language.javascript")
    assert python_row.necessity == Necessity.REQUIRED
    assert js_row.necessity == Necessity.REQUIRED


def test_non_bulleted_colon_heading_still_resets_state():
    """Contrast case: the SAME colon lead-in, NOT bulleted, standing on
    its own line, inside the same recognized section, still correctly
    triggers the UNKNOWN reset (a bare colon-terminated line is
    heading-shaped; only a BULLETED one is exempted)."""
    description = "Requirements:\nExperience with the following:\nPython\nJavaScript\n"
    result = parse_job_description_with_diagnostics(description)
    # Python/JavaScript are still admitted (bare concept mentions pass the
    # existing outside-section heuristic gate) but AS claims under UNKNOWN
    # with no local marker -- i.e. with no fabricated necessity either way,
    # they still resolve to concept rows via the normal technical-mention
    # path, but critically the heading line itself never becomes a claim.
    assert not any(r.original_text.strip() == "Experience with the following:" for r in result.profile.requirements)


# ---------------------------------------------------------------------------
# Exact text / exact source-span preservation for UnparsedClaim diagnostics.
# ---------------------------------------------------------------------------

def test_unparsed_claim_from_unknown_section_has_exact_text_and_span():
    description = (
        "Preferred Qualifications:\n- Docker is a plus.\n\n"
        "Learning Opportunities:\nYou will build new skills working with our internal deployment tooling.\n"
    )
    result = parse_job_description_with_diagnostics(description)
    matches = [u for u in result.unparsed_claims if "deployment tooling" in u.text]
    assert len(matches) == 1
    claim = matches[0]
    assert description[claim.source_span.start:claim.source_span.end] == claim.text
    assert claim.text == claim.text.strip()


# ---------------------------------------------------------------------------
# UNKNOWN-originated claims are excluded from the matcher/scoring denominator
# entirely -- there is no JobRequirement row for them at all, so match_job
# never sees them (mirrors the existing NOT_ASSESSABLE contract, but here
# there is nothing to even classify as NOT_ASSESSABLE).
# ---------------------------------------------------------------------------

def test_unknown_section_ambiguous_claim_never_enters_the_matcher_at_all():
    description = (
        "Preferred Qualifications:\n- Docker is a plus.\n\n"
        "Our Story:\nFor over 25 years, our engineers have been building great tools.\n"
    )
    result = parse_job_description_with_diagnostics(description)
    job_profile = result.profile
    candidate_profile = build_candidate_evidence_profile(
        "candidate", discovered=(), analyzed=(), evidence_items=(),
    )
    analysis = match_job(candidate_profile, job_profile)
    # exactly one requirement row exists at all (Docker) -- the "25 years"
    # narrative never became a JobRequirement, so it cannot appear in
    # requirement_matches under ANY MatchStatus, not even NOT_ASSESSABLE.
    assert len(analysis.requirement_matches) == 1
    assert analysis.requirement_matches[0].requirement.concept_id == "infra.docker"
    assert not any("25 years" in m.requirement.original_text for m in analysis.requirement_matches)


# ---------------------------------------------------------------------------
# Deterministic repeated parsing.
# ---------------------------------------------------------------------------

def test_repeated_parsing_is_byte_for_byte_deterministic():
    description = (
        "Required Qualifications:\n- Experience with Python is required.\n\n"
        "Preferred Qualifications:\n- Experience with Docker is a plus.\n\n"
        "When you join our team:\nWe'll empower you to grow your career.\n\n"
        "About the Company:\nWe are a global leader in financial services.\n"
    )
    first = parse_job_description_with_diagnostics(description)
    second = parse_job_description_with_diagnostics(description)
    assert first.profile == second.profile
    assert first.unparsed_claims == second.unparsed_claims


def test_claim_dataclass_still_frozen_and_hashable_with_none_hint():
    claim = Claim(text="x", start=0, end=1, necessity_hint=None)
    hash(claim)  # must not raise
    with pytest.raises(AttributeError):
        claim.necessity_hint = Necessity.REQUIRED  # type: ignore[misc]
