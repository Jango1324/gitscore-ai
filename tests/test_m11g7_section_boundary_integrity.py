"""Milestone 11-G7 -- section-boundary integrity.

Confirmed root cause (`docs/evaluation/MILESTONE_11_G7_SECTION_BOUNDARY_INTEGRITY.md`):
`segmentation.py`'s `_classify_heading_line()` rejects ANY heading-shaped
line exceeding 7 words -- uniformly, regardless of how strong its
structural signal (colon/ALL-CAPS/Markdown) is. When a genuine, long
heading is misjudged as ordinary content, `current_kind` (the single
forward-carrying loop state in `segment_description()`) never updates,
so whatever section was open BEFORE that line leaks across the boundary
into content AFTER it. Confirmed, by direct execution, to have THREE
severity tiers: LOW (stale UNKNOWN/LEARNING -> diagnostic-only, never
scored), and two HIGH tiers newly discovered by this milestone -- stale
REQUIRED/PREFERRED can fabricate an ASSESSABLE, SCORED JobRequirement
from pure responsibility prose naming a real technology; stale SKIP can
SILENTLY, TOTALLY SUPPRESS a genuine, locally-marked REQUIRED claim.

The fix (approved Option C, never an indiscriminate raise or an
unlimited removal): compute `has_strong_shape_signal` BEFORE the
word-count decision (a pure reordering), then branch the cap -- 14
words for strong-signal (colon/ALL-CAPS/Markdown) lines, 7 words
(unchanged) for weak-signal (bare title-case) lines. Measured (Phase 3
simulation, ported verbatim): 42/42 frozen controls match gold, 0
regressions, every adversarial lead-in/degenerate-run-on check passes.

This file consumes the FROZEN `evaluation/m11g7/boundary_controls.json`
corpus (42 independently-authored, synthetic controls; see that file's
own `correction_log` for the two pre-freeze self-correction rounds)
WITHOUT rewriting any of its expected outcomes -- written and run
against the real, unmodified classifier BEFORE the fix below was
implemented (confirmed failing on exactly the defect rows, then
passing after Strategy C was ported into `segmentation.py` verbatim).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from gitscore.assessment import assess_job
from gitscore.evidence import build_candidate_evidence_profile
from gitscore.jobs.parsing.parser import parse_job_description_with_diagnostics
from gitscore.jobs.parsing.segmentation import _classify_heading_line, _line_content_span
from gitscore.jobs.types import Necessity
from gitscore.matching import match_job

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "evaluation_lib"))
from gold_integrity import verify_frozen_file  # noqa: E402  (M11-G14)
GOLD_PATH = REPO_ROOT / "evaluation" / "m11g7" / "boundary_controls.json"
FREEZE_PATH = REPO_ROOT / "evaluation" / "m11g7" / "gold_hash_freeze.json"

pytestmark = pytest.mark.skipif(
    not GOLD_PATH.exists(),
    reason="M11-G7 boundary-controls corpus not present",
)

_GOLD = json.loads(GOLD_PATH.read_text(encoding="utf-8")) if GOLD_PATH.exists() else {"controls": []}
_CONTROLS = _GOLD["controls"]
_BY_ID = {c["id"]: c for c in _CONTROLS}
_CANDIDATE = build_candidate_evidence_profile("test", discovered=(), analyzed=(), evidence_items=())


def test_gold_hash_matches_freeze_record():
    # evaluation/m11g7/boundary_controls.json must never be edited to accommodate implementation.
    # M11-G14: the historical raw sha256/length are checked first; a checkout that differs ONLY by
    # CRLF<->LF conversion is accepted via the attested canonical manifest; anything else raises.
    verify_frozen_file(GOLD_PATH, FREEZE_PATH)


def _classify(heading_line: str | None) -> str:
    if heading_line is None:
        return "NOT_A_HEADING"
    span = _line_content_span(heading_line, 0)
    if span is None:
        return "NOT_A_HEADING"
    content = heading_line[span[0]:span[1]]
    result = _classify_heading_line(heading_line, content)
    return result.name if result is not None else "NOT_A_HEADING"


def _build_description(control: dict) -> str:
    lines = []
    if control["heading_line"] is not None:
        lines.append(control["heading_line"])
    lines.extend(control["body_lines"])
    return "\n".join(lines) + "\n"


def _describe(control_id: str) -> tuple[dict, str]:
    c = _BY_ID[control_id]
    return c, _build_description(c)


# ---------------------------------------------------------------------------
# 1. Full frozen-corpus parametrization -- exact heading-kind match,
#    gold's own expected value, never rewritten.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("control", _CONTROLS, ids=[c["id"] for c in _CONTROLS])
def test_frozen_control_heading_kind_matches_gold(control):
    actual = _classify(control["heading_line"])
    assert actual == control["expected_heading_kind"], (
        f"{control['id']}: heading {control['heading_line']!r} -- "
        f"expected {control['expected_heading_kind']!r}, got {actual!r}"
    )


@pytest.mark.parametrize("control", _CONTROLS, ids=[c["id"] for c in _CONTROLS])
def test_frozen_control_no_false_requirement_fabrication(control):
    """Category A/B/D (part): a non-qualification line must NEVER become
    a scored JobRequirement, regardless of what stale section state it
    inherits."""
    description = _build_description(control)
    parsed = parse_job_description_with_diagnostics(description)
    narrative_texts = {
        q["text"] for q in control["body_qualifications"] if not q["is_genuine_qualification"]
    }
    for req in parsed.profile.requirements:
        req_text = description[req.source_span.start:req.source_span.end]
        assert req_text not in narrative_texts, (
            f"{control['id']}: a non-qualification line was fabricated as a "
            f"scored JobRequirement: {req_text!r}"
        )


@pytest.mark.parametrize("control", _CONTROLS, ids=[c["id"] for c in _CONTROLS])
def test_frozen_control_no_silent_suppression(control):
    """Category C: a genuine qualification marked `should_enter_assessment`
    must be admitted as AT LEAST a diagnostic -- never silently, totally
    lost."""
    description = _build_description(control)
    parsed = parse_job_description_with_diagnostics(description)
    admitted_texts = (
        [description[r.source_span.start:r.source_span.end] for r in parsed.profile.requirements]
        + [description[u.source_span.start:u.source_span.end] for u in parsed.unparsed_claims]
    )
    for q in control["body_qualifications"]:
        if q["is_genuine_qualification"] and q["should_enter_assessment"]:
            found = any(q["text"] in t or t in q["text"] for t in admitted_texts)
            assert found, (
                f"{control['id']}: gold expects {q['text']!r} to be admitted "
                f"(JobRequirement or UnparsedClaim) but it was silently, "
                f"totally lost"
            )


# ---------------------------------------------------------------------------
# 2. Named anchor tests -- one per category (A-J) the approval explicitly
#    asked for, readable independently of the parametrized sweep above.
# ---------------------------------------------------------------------------


def test_category_a_required_carryforward_no_longer_fabricates_false_requirement():
    """A. FIXED by M11-G7: the previously-unrecognized long
    responsibility heading is now recognized, correctly resetting
    current_kind -- the responsibility sentence naming a real
    technology is no longer admitted unconditionally and no longer
    becomes a scored, assessable JobRequirement."""
    control, description = _describe("m11g7-019-severity-required-carryforward-HIGH")
    parsed = parse_job_description_with_diagnostics(description)
    fabricated_text = "Mentor junior engineers while writing production Python and Go services daily."
    fabricated = [
        r for r in parsed.profile.requirements
        if description[r.source_span.start:r.source_span.end] == fabricated_text
    ]
    assert len(fabricated) == 0, "the HIGH-severity fabrication must no longer reproduce"
    match = match_job(_CANDIDATE, parsed.profile)
    assessment = assess_job(match)
    assert assessment.assessable_count == 0
    assert assessment.alignment_score is None, (
        "no assessable requirement exists in this sub-document once the "
        "fabrication is eliminated -- alignment_score must be None, not a "
        "number computed from non-qualification prose"
    )


def test_category_b_preferred_carryforward_no_longer_fabricates_false_requirement():
    """B. FIXED by M11-G7: same defect shape under an inherited
    PREFERRED context no longer fabricates a requirement, while the
    genuine PREFERRED qualification on the first line is preserved."""
    control, description = _describe("m11g7-030-severity-preferred-carryforward")
    parsed = parse_job_description_with_diagnostics(description)
    fabricated_text = "Mentor junior engineers while writing production Rust services."
    fabricated = [
        r for r in parsed.profile.requirements
        if description[r.source_span.start:r.source_span.end] == fabricated_text
    ]
    assert len(fabricated) == 0, "the HIGH-severity PREFERRED-tier fabrication must no longer reproduce"
    genuine = [
        r for r in parsed.profile.requirements
        if description[r.source_span.start:r.source_span.end] == "Experience with Kubernetes is preferred."
    ]
    assert len(genuine) >= 1 and all(r.necessity == Necessity.PREFERRED for r in genuine), (
        "the genuine PREFERRED qualification must still be preserved"
    )


def test_category_c_skip_carryforward_no_longer_silently_suppresses_requirement():
    """C. FIXED by M11-G7: the previously-unrecognized long heading is
    now recognized, correctly resetting current_kind away from stale
    SKIP -- the genuine, locally-marked REQUIRED qualification is now
    recovered as a real, scored JobRequirement instead of being
    silently, totally lost."""
    control, description = _describe("m11g7-020-severity-skip-carryforward-HIGH")
    parsed = parse_job_description_with_diagnostics(description)
    recovered = [
        r for r in parsed.profile.requirements
        if description[r.source_span.start:r.source_span.end]
        == "Experience with Python and distributed systems is required."
    ]
    assert len(recovered) >= 1, "the genuine REQUIRED qualification must now be recovered"
    assert all(r.necessity == Necessity.REQUIRED for r in recovered)
    match = match_job(_CANDIDATE, parsed.profile)
    assessment = assess_job(match)
    assert assessment.assessable_count >= 1
    assert assessment.alignment_score == 0, (
        "the recovered requirement is now genuinely assessable -- this "
        "deterministic, empty candidate fixture correctly scores 0% on a "
        "real requirement it shows no evidence for (NOT a defect -- the "
        "correct, intended effect of fixing a false-negative admission gap)"
    )


def test_category_d_unknown_carryforward_is_diagnostic_only_never_scored():
    """D. The LOW-severity tier: a stale UNKNOWN/LEARNING state across an
    unrecognized long heading admits responsibility content at worst as
    a diagnostic UnparsedClaim -- never a scored JobRequirement."""
    control, description = _describe("m11g7-018-severity-unknown-carryforward")
    parsed = parse_job_description_with_diagnostics(description)
    narrative_texts = {
        q["text"] for q in control["body_qualifications"] if not q["is_genuine_qualification"]
    }
    for req in parsed.profile.requirements:
        assert description[req.source_span.start:req.source_span.end] not in narrative_texts


def test_category_e_genuine_long_strong_signal_headings_now_recognized():
    """E. FIXED by M11-G7: genuine headings longer than 7 words with
    strong structural markers (colon/Markdown/ALL-CAPS) are now
    correctly recognized, matching gold's own expected family."""
    for cid in (
        "m11g7-005-long-required-colon-10words",
        "m11g7-006-long-preferred-colon-8words",
        "m11g7-010-long-allcaps-9words",
    ):
        control = _BY_ID[cid]
        actual = _classify(control["heading_line"])
        assert actual == control["expected_heading_kind"], cid
        assert actual != "NOT_A_HEADING", cid


def test_category_f_long_leadin_sentences_must_never_become_headings():
    """F. Long colon-terminated lead-in sentences introducing a sub-list
    from INSIDE an already-open section must never be classified as
    headings -- confirmed correct today (the baseline this fix must
    preserve, not regress)."""
    for cid in (
        "m11g7-014-leadin-not-heading-required-section",
        "m11g7-015-leadin-not-heading-responsibility-section",
        "m11g7-037-leadin-not-heading-inside-skip-section",
    ):
        control = _BY_ID[cid]
        leadin_text = control["body_lines"][0]
        assert _classify(leadin_text) == "NOT_A_HEADING", cid


def test_category_g_bare_one_word_qualification_after_leadin_stays_in_section():
    """G. A bare, one-word-per-line qualification value following a long
    lead-in sentence must remain inside its real REQUIRED section --
    confirmed correct today."""
    control, description = _describe("m11g7-014-leadin-not-heading-required-section")
    parsed = parse_job_description_with_diagnostics(description)
    python_reqs = [
        r for r in parsed.profile.requirements
        if description[r.source_span.start:r.source_span.end] == "Python"
    ]
    assert len(python_reqs) >= 1
    assert all(r.necessity == Necessity.REQUIRED for r in python_reqs)


def test_category_h_degenerate_long_run_on_never_becomes_a_heading():
    """H. A deliberately degenerate 42-word run-on clause ending in a
    bare colon must never be classified as a heading, today or after
    any fix."""
    control = _BY_ID["m11g7-027-degenerate-very-long-colon-line"]
    runon_text = control["body_lines"][0]
    assert _classify(runon_text) == "NOT_A_HEADING"


def test_category_i_already_correct_short_headings_and_transitions_unaffected():
    """I. Already-correct short headings, section transitions, and
    necessity inference are unaffected baselines."""
    assert _classify("Required Qualifications:") == "REQUIRED"
    assert _classify("What You'll Do:") == "RESPONSIBILITY"
    control, description = _describe("m11g7-021-transition-long-heading-resets-correctly")
    parsed = parse_job_description_with_diagnostics(description)
    assert any(r.necessity == Necessity.PREFERRED for r in parsed.profile.requirements)
    mentor_texts = {description[u.source_span.start:u.source_span.end] for u in parsed.unparsed_claims}
    assert "Mentor junior engineers." in mentor_texts


def test_category_j_exact_source_spans_preserved():
    """J. Source spans for admitted claims are exact, direct slices of
    the original description text -- a pure sanity check unrelated to
    the heading-length defect (span computation never reads
    section_kind at all)."""
    control, description = _describe("m11g7-001-short-required-colon")
    parsed = parse_job_description_with_diagnostics(description)
    assert len(parsed.profile.requirements) >= 1
    for r in parsed.profile.requirements:
        text = description[r.source_span.start:r.source_span.end]
        assert text == r.original_text or text.strip() == r.original_text.strip()
