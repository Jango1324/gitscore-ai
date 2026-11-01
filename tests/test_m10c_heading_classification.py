"""Milestone 10C -- real-world heading recognition.

Covers the approved design in
`docs/evaluation/MILESTONE_10C_SECTION_CLASSIFICATION.md`:
`segmentation.py`'s `_classify_heading_line()` (structural shape gate +
anchored root-word families, replacing the old small exact-phrase
table), the new `_SectionKind.LEARNING`, and the generalized
`NON_QUALIFICATION` vocabulary (the existing `SKIP` kind).

Two independently-authored control sets are exercised against the REAL,
shipped classifier -- never against a candidate design:

- `evaluation/m10c/heading_controls.json` (78 entries) -- the SAME
  corpus used to select Strategy C in the design review. Loaded here,
  unedited, as a genuine regression suite.
- `evaluation/m10c/heading_controls_heldout.json` (18 entries) --
  written AFTER Strategy C was already selected and implemented,
  specifically so it could not have influenced that selection. Fresh
  phrasing throughout (a fifth fictional company, new idiom variants,
  bare one-word/two-word list-item negative controls targeting the
  exact regression this milestone's own implementation found), never
  edited to match whatever the shipped code happens to do.

Both are scored with the SAME three-tier outcome used in the design
review's own evaluation harness (never a flat pass/fail): `exact_match`,
`safe_disagreement` (wrong, but never a confidently-wrong named family),
or `unsafe_mismatch` (a scoring-relevant family confidently assigned
against the control's own truth). The hard, asserted regression
guarantee for BOTH corpora is zero `unsafe_mismatch` entries -- `safe_disagreement`
on a genuinely ambiguous or family-root-less heading is an accepted,
documented limitation (see the design doc's completion addendum), not a
test failure.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gitscore.jobs.parsing.necessity import infer_necessity
from gitscore.jobs.parsing.parser import parse_job_description_with_diagnostics
from gitscore.jobs.parsing.segmentation import _SectionKind, _classify_heading_line, segment_description

REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_CORPUS_PATH = REPO_ROOT / "evaluation" / "m10c" / "heading_controls.json"
HELDOUT_CORPUS_PATH = REPO_ROOT / "evaluation" / "m10c" / "heading_controls_heldout.json"

_SCORING_RELEVANT_SECTIONS = {"REQUIRED", "PREFERRED", "RESPONSIBILITY", "LEARNING", "NON_QUALIFICATION"}

_KIND_TO_SECTION = {
    _SectionKind.REQUIRED: "REQUIRED",
    _SectionKind.PREFERRED: "PREFERRED",
    _SectionKind.RESPONSIBILITY: "RESPONSIBILITY",
    _SectionKind.LEARNING: "LEARNING",
    _SectionKind.SKIP: "NON_QUALIFICATION",
    _SectionKind.UNKNOWN: "UNKNOWN",
}


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["controls"]


def _classify(text: str) -> tuple[bool, str | None]:
    """(is_heading, section_name) for one raw line, via the REAL, shipped
    `_classify_heading_line` -- never a candidate design.
    """
    kind = _classify_heading_line(text, text)
    if kind is None:
        return False, None
    return True, _KIND_TO_SECTION[kind]


def _acceptable_sections(entry: dict) -> set[str]:
    base = {entry["expected_section"]} if entry.get("expected_section") else set()
    base |= set(entry.get("acceptable_sections", []))
    return base


def _outcome_tier(entry: dict, is_heading: bool, section: str | None) -> str:
    truth_is_heading = entry["is_heading"]
    truth_section = entry.get("expected_section")
    ambiguous = entry.get("ambiguous", False)
    acceptable = _acceptable_sections(entry)

    if not truth_is_heading:
        if not is_heading:
            return "exact_match"
        if section == "UNKNOWN":
            return "safe_disagreement"
        return "unsafe_mismatch"

    if not is_heading:
        # Accepted, documented tradeoff (see segmentation.py's own
        # comments and the design doc's completion addendum): a bare,
        # family-root-less, weak-signal-only heading (truth itself
        # UNKNOWN -- "Additional Information") is never heading-shaped
        # under this milestone's own regression fix for the "Python" bare
        # list-item collision. Missing detection of a NAMED family
        # (REQUIRED/PREFERRED/RESPONSIBILITY/LEARNING/NON_QUALIFICATION)
        # is a real, unsafe miss; missing an already-UNKNOWN-truth or
        # already-ambiguous heading is not -- it was never going to
        # produce a scoring-relevant outcome either way.
        if ambiguous or truth_section == "UNKNOWN":
            return "safe_disagreement"
        return "unsafe_mismatch"

    if section in acceptable:
        return "exact_match"
    if section == "UNKNOWN":
        return "safe_disagreement"
    return "unsafe_mismatch"


_MAIN_CONTROLS = _load(MAIN_CORPUS_PATH)
_HELDOUT_CONTROLS = _load(HELDOUT_CORPUS_PATH)


@pytest.mark.parametrize("control", _MAIN_CONTROLS, ids=[c["id"] for c in _MAIN_CONTROLS])
def test_main_corpus_control_never_unsafe(control):
    is_heading, section = _classify(control["text"])
    tier = _outcome_tier(control, is_heading, section)
    assert tier != "unsafe_mismatch", (
        f"{control['id']}: {control['text']!r} -- expected one of "
        f"{_acceptable_sections(control) or {'NOT_A_HEADING'}!r}, got "
        f"({is_heading}, {section!r}) -- a scoring-relevant family confidently "
        "assigned against this control's own truth"
    )


@pytest.mark.parametrize("control", _HELDOUT_CONTROLS, ids=[c["id"] for c in _HELDOUT_CONTROLS])
def test_heldout_corpus_control_never_unsafe(control):
    is_heading, section = _classify(control["text"])
    tier = _outcome_tier(control, is_heading, section)
    assert tier != "unsafe_mismatch", (
        f"{control['id']}: {control['text']!r} -- expected one of "
        f"{_acceptable_sections(control) or {'NOT_A_HEADING'}!r}, got "
        f"({is_heading}, {section!r})"
    )


def test_main_corpus_exact_match_rate_matches_measured_report():
    """Pins the measured Phase 3 result (post-implementation-fix numbers,
    not the pre-fix design-review draft) so a future change to the
    classifier is forced to consciously update this number, not silently
    drift it. See docs/evaluation/MILESTONE_10C_SECTION_CLASSIFICATION.md's
    completion addendum for the full accounting of the one accepted
    `safe_disagreement` ("Additional Information", family-root-less).
    """
    exact = sum(
        1 for c in _MAIN_CONTROLS
        if _outcome_tier(c, *_classify(c["text"])) == "exact_match"
    )
    assert exact == 72  # of 78 -- 5 safe_disagreement, 0 unsafe_mismatch (see evaluation report)


def test_heldout_corpus_all_exact_or_safe():
    tiers = [_outcome_tier(c, *_classify(c["text"])) for c in _HELDOUT_CONTROLS]
    assert all(t in ("exact_match", "safe_disagreement") for t in tiers)


# ---------------------------------------------------------------------------
# Section transitions across all six kinds, including the two new ones.
# ---------------------------------------------------------------------------


def test_required_skills_heading_now_recognized():
    description = "Required skills:\n- Experience with Python is needed.\n"
    claim = segment_description(description)[0]
    assert claim.necessity_hint.value == "required"


def test_preferred_background_heading_recognized():
    description = "Preferred Background:\n- Experience with Redis.\n"
    claim = segment_description(description)[0]
    assert claim.necessity_hint.value == "preferred"


def test_position_responsibilities_heading_now_recognized():
    description = "Position Responsibilities:\n- Write and review pull requests.\n"
    claim = segment_description(description)[0]
    assert claim.necessity_hint.value == "required"  # RESPONSIBILITY's existing hint, unchanged


def test_learning_heading_never_defaults_a_necessity():
    description = "What You Will Learn:\nYou will build new skills working with our internal tooling.\n"
    claims = segment_description(description)
    assert len(claims) == 1
    assert claims[0].necessity_hint is None


def test_non_qualification_heading_fully_suppresses_content():
    description = (
        "Requirements:\n- Python is required.\n\n"
        "Compensation Disclosure:\nSalary depends on skills, qualifications, and experience.\n"
    )
    claims = segment_description(description)
    assert len(claims) == 1
    assert claims[0].text == "Python is required."


def test_about_fictional_company_heading_recognized_as_non_qualification():
    description = (
        "Requirements:\n- Go is required.\n\n"
        "About Driftwood Analytics:\nWe build tools for logistics teams worldwide.\n"
    )
    claims = segment_description(description)
    assert len(claims) == 1
    assert claims[0].text == "Go is required."


def test_unrecognized_heading_still_resolves_to_unknown():
    description = (
        "Requirements:\n- Python is required.\n\n"
        "Flexible Work Policy:\nThis role offers flexible scheduling and skills growth.\n"
    )
    result = parse_job_description_with_diagnostics(description)
    policy_rows = [r for r in result.profile.requirements if "flexible scheduling" in r.original_text]
    assert policy_rows == []  # never a scored JobRequirement
    policy_unparsed = [u for u in result.unparsed_claims if "flexible scheduling" in u.text]
    assert len(policy_unparsed) == 1  # admitted (contains "skills"), diagnostic only


def test_recognized_section_after_learning_is_not_sticky():
    description = (
        "Learning Opportunities:\nYou will grow your skills in cloud infrastructure.\n\n"
        "Required Qualifications:\n- Experience with AWS is required.\n"
    )
    claims = segment_description(description)
    aws_claim = next(c for c in claims if "AWS" in c.text)
    assert aws_claim.necessity_hint.value == "required"


def test_learning_section_does_not_stay_sticky_into_unknown_then_required():
    description = (
        "Learning Opportunities:\nYou will grow your skills in cloud infrastructure.\n\n"
        "Random Notes:\nThis section has no recognized family.\n\n"
        "Requirements:\n- Docker is required.\n"
    )
    claims = segment_description(description)
    docker_claim = next(c for c in claims if "Docker" in c.text)
    assert docker_claim.necessity_hint.value == "required"


# ---------------------------------------------------------------------------
# Unicode, Markdown, and bullet formatting.
# ---------------------------------------------------------------------------


def test_markdown_heading_leader_recognized():
    description = "## Required Qualifications\n- Python is needed.\n"
    claim = segment_description(description)[0]
    assert claim.necessity_hint.value == "required"


def test_markdown_bold_heading_recognized():
    description = "**Preferred Qualifications**\n- Redis experience.\n"
    claim = segment_description(description)[0]
    assert claim.necessity_hint.value == "preferred"


def test_nbsp_heading_recognized():
    description = "Required Qualifications:\n- Python is needed.\n"
    claim = segment_description(description)[0]
    assert claim.necessity_hint.value == "required"


def test_zero_width_space_heading_recognized():
    description = "Required Qualifications​\n- Python is needed.\n"
    claim = segment_description(description)[0]
    assert claim.necessity_hint.value == "required"


def test_bulleted_heading_shaped_line_is_never_a_heading():
    description = "Requirements:\n- Compensation\n- Python\n"
    claims = segment_description(description)
    texts = [c.text for c in claims]
    assert "Compensation" in texts  # a bulleted line is a list item, never a heading
    assert "Python" in texts


def test_bare_list_item_single_word_never_swallowed_as_heading():
    """The exact regression this milestone's own implementation caught."""
    description = "Requirements:\nPython\nPostgreSQL\nDocker\n"
    claims = segment_description(description)
    assert [c.text for c in claims] == ["Python", "PostgreSQL", "Docker"]


def test_inline_colon_requirement_claim_never_a_heading():
    description = "Requirements:\nExperience with: Python, JavaScript\n"
    claims = segment_description(description)
    assert len(claims) == 1
    assert claims[0].text == "Experience with: Python, JavaScript"


# ---------------------------------------------------------------------------
# No qualification rows from LEARNING or NON_QUALIFICATION sections.
# ---------------------------------------------------------------------------


def test_learning_section_never_produces_a_scored_requirement():
    description = (
        "What You Will Learn:\n"
        "Enhance your programming skills by working alongside experienced team members.\n"
    )
    result = parse_job_description_with_diagnostics(description)
    assert result.profile.requirements == ()


def test_non_qualification_section_never_produces_a_scored_requirement():
    description = (
        "About Us:\nWe are revolutionizing the industry with cutting-edge Python and AWS technology.\n"
    )
    result = parse_job_description_with_diagnostics(description)
    assert result.profile.requirements == ()


def test_local_marker_still_overrides_learning_section_hint():
    """Milestone 6B Part 7's precedence, unchanged: explicit local wording
    still wins even under the new LEARNING kind."""
    description = "Learning Opportunities:\nExperience with Terraform is required.\n"
    result = parse_job_description_with_diagnostics(description)
    rows = [r for r in result.profile.requirements if r.concept_id == "devops.terraform" or r.concept_id is not None]
    assert any(r.necessity.value == "required" for r in result.profile.requirements)


# ---------------------------------------------------------------------------
# Source-span fidelity and determinism.
# ---------------------------------------------------------------------------


def test_claim_spans_remain_exact_offsets_with_new_headings():
    description = (
        "Position Responsibilities:\n- Write and review pull requests.\n\n"
        "What You Will Learn:\nYou will build new skills in distributed systems.\n\n"
        "Required Qualifications:\n- Experience with PostgreSQL is required.\n"
    )
    for claim in segment_description(description):
        assert description[claim.start:claim.end] == claim.text
        assert claim.text == claim.text.strip()


def test_heading_lines_never_become_claims_across_all_new_kinds():
    description = (
        "## Required Qualifications\n- Python is required.\n\n"
        "What You Will Learn:\nYou will grow your skills.\n\n"
        "About Us:\nWe build great things.\n\n"
        "Working Arrangement:\nThis role is hybrid.\n"
    )
    for claim in segment_description(description):
        normalized = claim.text.strip().lower()
        assert normalized not in (
            "required qualifications", "what you will learn", "about us", "working arrangement",
        )


def test_determinism_across_repeated_parses():
    description = (
        "Position Responsibilities:\n- Deploy services to production.\n\n"
        "Required Qualifications:\n- Experience with Go is required.\n"
    )
    first = segment_description(description)
    second = segment_description(description)
    assert first == second


def test_infer_necessity_unaffected_by_new_section_kinds():
    """necessity.py's own precedence logic is untouched by M10C -- this is
    a pure sanity check, not new behavior."""
    assert infer_necessity("Python is required.", None).value == "required"
    assert infer_necessity("Python is a plus.", None).value == "preferred"
    assert infer_necessity("Python experience.", None) is None
