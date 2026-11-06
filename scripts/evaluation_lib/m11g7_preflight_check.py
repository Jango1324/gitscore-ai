"""Milestone 11-G7 pre-freeze sanity check -- verifies every control's
own authored `heading_word_count`/`has_strong_shape_signal` metadata
against the REAL `_classify_heading_line` internals, and prints the
REAL current classification for every control, so authoring mistakes
can be caught and fixed BEFORE the hash freeze (minimizing post-freeze
correction rounds, learned from M11-G6's own three-round process).

Evaluation-only. Run BEFORE freezing; never informs gold's own
`expected_heading_kind` by what the current (possibly defective) code
outputs -- only cross-checks the STRUCTURAL metadata fields, which are
objective facts about the text, not judgment calls.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gitscore.jobs.parsing.segmentation import (  # noqa: E402
    _classify_heading_line,
    _line_content_span,
    _strip_heading_decoration,
)

GOLD_PATH = REPO_ROOT / "evaluation" / "m11g7" / "boundary_controls.json"


def real_word_count_and_signal(heading_line: str) -> tuple[int, bool]:
    span = _line_content_span(heading_line, 0)
    content = heading_line[span[0]:span[1]]
    decorated = _strip_heading_decoration(content)
    ends_with_colon = decorated.endswith(":")
    content_no_colon = decorated[:-1].strip() if ends_with_colon else decorated
    word_count = len(content_no_colon.split())
    is_all_caps = any(ch.isalpha() for ch in content_no_colon) and all(
        (not ch.isalpha()) or ch.isupper() for ch in content_no_colon
    )
    is_markdown_or_bold = decorated != content.strip()
    strong = ends_with_colon or is_all_caps or is_markdown_or_bold
    return word_count, strong


def main() -> None:
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    mismatches = []
    for c in gold["controls"]:
        if c["heading_line"] is None:
            current = "N/A (no heading_line)"
        else:
            real_wc, real_strong = real_word_count_and_signal(c["heading_line"])
            if real_wc != c["heading_word_count"] or real_strong != c["has_strong_shape_signal"]:
                mismatches.append((c["id"], "authored", c["heading_word_count"], c["has_strong_shape_signal"],
                                    "real", real_wc, real_strong))
            span = _line_content_span(c["heading_line"], 0)
            content = c["heading_line"][span[0]:span[1]]
            result = _classify_heading_line(c["heading_line"], content)
            current = result.name if result is not None else "NOT_A_HEADING"
        print(f"{c['id']:55s} expected={c['expected_heading_kind']:16s} current_real={current}")

    print()
    print(f"=== metadata mismatches ({len(mismatches)}) ===")
    for m in mismatches:
        print(m)


if __name__ == "__main__":
    main()
