"""Milestone 11-G7 Phase 3 -- simulates four candidate fixes (including
the current baseline) against the frozen `boundary_controls.json`
corpus WITHOUT touching `src/gitscore` at all. Each strategy
re-implements `_classify_heading_line`'s own control flow, reusing
every real helper/regex via import (never retyped), changing ONLY the
word-count decision.

Evaluation-only. No production file is modified or monkey-patched.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gitscore.jobs.parsing.segmentation import (  # noqa: E402
    _BULLET_PREFIX,
    _has_inline_colon_list,
    _is_titlecase_heading,
    _matched_heading_families,
    _strip_heading_decoration,
    _SectionKind,
)

GOLD_PATH = REPO_ROOT / "evaluation" / "m11g7" / "boundary_controls.json"
FREEZE_PATH = REPO_ROOT / "evaluation" / "m11g7" / "gold_hash_freeze.json"
OUT_PATH = REPO_ROOT / "evaluation" / "reports" / "m11g7_phase3_strategy_comparison.json"

_SENTENCE_TERMINAL = re.compile(r"[.!?]\s*$")

# A strategy-chosen bound for Strategy C ("bounded raise for strong
# signal only") -- 14 words, chosen to comfortably cover every genuine
# long heading authored in this corpus (max 13 words, control 029/042)
# with one word of margin, while still rejecting the deliberately
# degenerate 42-word run-on (control 027) and the 17/18-word lead-in
# sentences (014/015/037).
STRATEGY_C_STRONG_SIGNAL_CAP = 14


def _shape_gate_common(line: str, content: str) -> tuple[str, bool, bool] | None:
    """Everything in `_classify_heading_line` BEFORE the word-count
    decision -- returns (content_no_colon, has_strong_shape_signal,
    ends_with_bare_colon) or None if already rejected by a check that
    is NEVER touched by any G7 strategy (bullet/empty/sentence-
    terminal/inline-colon-list)."""
    if _BULLET_PREFIX.match(line) is not None:
        return None
    decorated = _strip_heading_decoration(content)
    if not decorated:
        return None
    if _SENTENCE_TERMINAL.search(decorated):
        return None
    if _has_inline_colon_list(decorated):
        return None
    ends_with_bare_colon = decorated.endswith(":")
    content_no_colon = decorated[:-1].strip() if ends_with_bare_colon else decorated
    is_all_caps = any(ch.isalpha() for ch in content_no_colon) and all(
        (not ch.isalpha()) or ch.isupper() for ch in content_no_colon
    )
    is_markdown_or_bold = decorated != content.strip()
    has_strong_shape_signal = ends_with_bare_colon or is_all_caps or is_markdown_or_bold
    return content_no_colon, has_strong_shape_signal


def _resolve_families(content_no_colon: str, has_strong_shape_signal: bool) -> _SectionKind | None:
    is_plain_titlecase = _is_titlecase_heading(content_no_colon)
    if not has_strong_shape_signal and not is_plain_titlecase:
        return None
    families = _matched_heading_families(content_no_colon)
    if not has_strong_shape_signal and not families:
        return None
    if len(families) == 1:
        return families[0]
    return _SectionKind.UNKNOWN


def classify_current(line: str, content: str) -> _SectionKind | None:
    """Byte-faithful reimplementation of the REAL, shipped function --
    word_count > 7 rejects regardless of signal strength."""
    gate = _shape_gate_common(line, content)
    if gate is None:
        return None
    content_no_colon, has_strong_shape_signal = gate
    word_count = len(content_no_colon.split())
    if word_count == 0 or word_count > 7:
        return None
    return _resolve_families(content_no_colon, has_strong_shape_signal)


def classify_strategy_a_naive_raise(line: str, content: str) -> _SectionKind | None:
    """Option A (strawman, explicitly warned against by the mission
    brief): uniformly raise the cap to a generous number for EVERY
    heading-shaped line regardless of signal strength."""
    gate = _shape_gate_common(line, content)
    if gate is None:
        return None
    content_no_colon, has_strong_shape_signal = gate
    word_count = len(content_no_colon.split())
    if word_count == 0 or word_count > 20:
        return None
    return _resolve_families(content_no_colon, has_strong_shape_signal)


def classify_strategy_b_uncapped_strong_signal(line: str, content: str) -> _SectionKind | None:
    """Option B: remove the word-count cap ENTIRELY for strong-signal
    (colon/ALL-CAPS/Markdown) lines; keep the existing <=7-word cap for
    weak-signal (bare title-case) lines unchanged."""
    gate = _shape_gate_common(line, content)
    if gate is None:
        return None
    content_no_colon, has_strong_shape_signal = gate
    word_count = len(content_no_colon.split())
    if word_count == 0:
        return None
    if not has_strong_shape_signal and word_count > 7:
        return None
    return _resolve_families(content_no_colon, has_strong_shape_signal)


def classify_strategy_c_bounded_raise_strong_signal(line: str, content: str) -> _SectionKind | None:
    """Option C (recommended candidate): raise the cap to a bounded,
    still-finite limit (STRATEGY_C_STRONG_SIGNAL_CAP) for strong-signal
    lines only; keep the existing <=7-word cap for weak-signal lines
    unchanged. Never unbounded -- the degenerate 42-word run-on
    (control 027) must still be rejected."""
    gate = _shape_gate_common(line, content)
    if gate is None:
        return None
    content_no_colon, has_strong_shape_signal = gate
    word_count = len(content_no_colon.split())
    if word_count == 0:
        return None
    cap = STRATEGY_C_STRONG_SIGNAL_CAP if has_strong_shape_signal else 7
    if word_count > cap:
        return None
    return _resolve_families(content_no_colon, has_strong_shape_signal)


STRATEGIES = {
    "current": classify_current,
    "A_naive_uniform_raise_to_20": classify_strategy_a_naive_raise,
    "B_uncapped_strong_signal": classify_strategy_b_uncapped_strong_signal,
    "C_bounded_raise_strong_signal_14": classify_strategy_c_bounded_raise_strong_signal,
}


def classify(heading_line: str | None, strategy_fn) -> str:
    if heading_line is None:
        return "NOT_A_HEADING"
    # mirror _line_content_span: trim leading/trailing whitespace only
    stripped = heading_line.strip()
    if not stripped:
        return "NOT_A_HEADING"
    result = strategy_fn(heading_line, heading_line)
    return result.name if result is not None else "NOT_A_HEADING"


def main() -> None:
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "evaluation_lib"))
    from gold_integrity import verify_frozen_file  # M11-G14: line-ending-portable; raises if gold drifted
    verify_frozen_file(GOLD_PATH, FREEZE_PATH)

    rows = []
    summary = {name: {"matches_gold": 0, "regressions_vs_current": 0, "fixes_vs_current": 0}
               for name in STRATEGIES}

    for control in gold["controls"]:
        heading = control["heading_line"]
        expected = control["expected_heading_kind"]
        row = {"id": control["id"], "category": control["category"], "expected": expected}
        current_val = None
        for name, fn in STRATEGIES.items():
            val = classify(heading, fn)
            row[name] = val
            if name == "current":
                current_val = val
        rows.append(row)

        for name in STRATEGIES:
            val = row[name]
            if val == expected:
                summary[name]["matches_gold"] += 1
            if name != "current":
                if val != current_val and val != expected:
                    summary[name]["regressions_vs_current"] += 1
                if val != current_val and val == expected and current_val != expected:
                    summary[name]["fixes_vs_current"] += 1

    # The critical adversarial check: for the lead-in-not-a-heading
    # controls (014, 015, 037), does each strategy correctly LEAVE the
    # lead-in sentence unrecognized (preserving the already-open
    # section), or does it wrongly promote the lead-in to a NEW heading
    # (which would demote the following one-word-per-line value out of
    # its real section)?
    leadin_ids = {
        "m11g7-014-leadin-not-heading-required-section",
        "m11g7-015-leadin-not-heading-responsibility-section",
        "m11g7-037-leadin-not-heading-inside-skip-section",
    }
    leadin_results = {}
    for control in gold["controls"]:
        if control["id"] not in leadin_ids:
            continue
        leadin_text = control["body_lines"][0]
        per_strategy = {}
        for name, fn in STRATEGIES.items():
            val = classify(leadin_text, fn)
            per_strategy[name] = val
        leadin_results[control["id"]] = per_strategy

    # The degenerate run-on check (control 027).
    degenerate = next(c for c in gold["controls"] if c["id"] == "m11g7-027-degenerate-very-long-colon-line")
    degenerate_text = degenerate["body_lines"][0]
    degenerate_results = {name: classify(degenerate_text, fn) for name, fn in STRATEGIES.items()}

    out = {
        "corpus_version": gold["corpus_version"],
        "n_controls": len(gold["controls"]),
        "summary": summary,
        "adversarial_leadin_results": leadin_results,
        "adversarial_leadin_note": (
            "NOT_A_HEADING is the SAFE outcome for every lead-in -- it "
            "means the lead-in sentence does NOT reset current_kind away "
            "from the section it is actually inside of. Any OTHER value "
            "(UNKNOWN/REQUIRED/etc.) means the strategy WRONGLY promoted "
            "this lead-in to a new heading, which would demote the "
            "following one-item-per-line value out of its real section."
        ),
        "degenerate_runon_results": degenerate_results,
        "degenerate_runon_note": (
            "NOT_A_HEADING is the SAFE outcome. Any other value means the "
            "strategy heading-ified a 42-word run-on clause."
        ),
        "rows": rows,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("adversarial lead-in results:")
    print(json.dumps(leadin_results, indent=2))
    print("degenerate run-on results:")
    print(json.dumps(degenerate_results, indent=2))
    print(f"wrote {len(rows)} rows to {OUT_PATH}")


if __name__ == "__main__":
    main()
