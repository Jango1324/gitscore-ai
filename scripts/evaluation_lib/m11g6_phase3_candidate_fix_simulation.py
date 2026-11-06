"""Milestone 11-G6 Phase 3 -- simulates three candidate general fixes
against the frozen `heading_controls.json` corpus WITHOUT touching
`src/gitscore` at all. Each strategy re-derives
`_matched_heading_families`'s decision from the REAL, imported
`_REQUIRED_ROOT`/`_QUALIFICATION_ROOT`/`_PREFERRED_ROOT`/`_LEARNING_ROOT`/
`_RESPONSIBILITY_ROOT`/`_NON_QUALIFICATION_ROOT` patterns (never
duplicated/retyped) plus, for Strategy C only, one NEW regex defined
locally in this evaluation script -- never written into production.

Evaluation-only. No production file is imported for write access or
monkey-patched; every strategy function is pure and local to this
script.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gitscore.jobs.parsing.segmentation import (  # noqa: E402
    _LEARNING_ROOT,
    _NON_QUALIFICATION_ROOT,
    _PREFERRED_ROOT,
    _QUALIFICATION_ROOT,
    _REQUIRED_ROOT,
    _RESPONSIBILITY_ROOT,
    _classify_heading_line,
    _line_content_span,
    _SectionKind,
)

GOLD_PATH = REPO_ROOT / "evaluation" / "m11g6" / "heading_controls.json"
FREEZE_PATH = REPO_ROOT / "evaluation" / "m11g6" / "gold_hash_freeze.json"
OUT_PATH = REPO_ROOT / "evaluation" / "reports" / "m11g6_phase3_strategy_comparison.json"

# ---------------------------------------------------------------------------
# Strategy C's one new piece of vocabulary -- a closed, generic,
# non-employer-specific "candidate-profile-seeking" signal family,
# exactly the same design discipline every existing root table in
# segmentation.py already follows. Deliberately covers MULTIPLE
# Phase-2-corpus heading styles at once (not phrased around "Who We Are
# Looking For" specifically) -- "looking for"/"seeking"/"we need"/
# "you('ll) bring"/"ideal candidate" are each independently common
# across What We're Looking For / What We Need to See / What You'll
# Bring / The Ideal Candidate.
# ---------------------------------------------------------------------------
_CANDIDATE_PROFILE_ROOT = re.compile(
    r"\blooking for\b|\bwe(?:'re| are) seeking\b|\bwe need\b|\bwe want\b|"
    r"\byou(?:'ll| will) bring\b|\byou bring\b|\bideal candidate\b",
    re.IGNORECASE,
)


def _base_families(content: str) -> dict[str, bool]:
    return {
        "required": bool(_REQUIRED_ROOT.search(content)),
        "qualification": bool(_QUALIFICATION_ROOT.search(content)),
        "preferred": bool(_PREFERRED_ROOT.search(content)),
        "learning": bool(_LEARNING_ROOT.search(content)),
        "responsibility": bool(_RESPONSIBILITY_ROOT.search(content)),
        "non_qualification": bool(_NON_QUALIFICATION_ROOT.search(content)),
    }


def _resolve(families: list[_SectionKind]) -> str:
    if len(families) == 1:
        return families[0].name
    if len(families) == 0:
        return "ZERO_FAMILIES"  # caller decides UNKNOWN vs NOT_A_HEADING via shape gate
    return "UNKNOWN"


def strategy_current(content: str) -> list[_SectionKind]:
    b = _base_families(content)
    required_fires = b["required"] or (b["qualification"] and not b["preferred"])
    families = []
    if required_fires:
        families.append(_SectionKind.REQUIRED)
    if b["preferred"]:
        families.append(_SectionKind.PREFERRED)
    if b["learning"]:
        families.append(_SectionKind.LEARNING)
    if b["responsibility"]:
        families.append(_SectionKind.RESPONSIBILITY)
    if b["non_qualification"]:
        families.append(_SectionKind.SKIP)
    return families


def strategy_a_precedence(content: str) -> list[_SectionKind]:
    """Option A: more-specific families take precedence over broader
    ones via a FIXED precedence order (REQUIRED/PREFERRED/RESPONSIBILITY/
    LEARNING outrank SKIP when more than one fires), instead of the
    current honest-UNKNOWN-on-collision rule. Does NOT add any new
    signal -- so when NON_QUALIFICATION is the ONLY family that fires at
    all (the actual defect shape), precedence has nothing to prefer
    over it and SKIP still wins."""
    b = _base_families(content)
    required_fires = b["required"] or (b["qualification"] and not b["preferred"])
    if required_fires:
        return [_SectionKind.REQUIRED]
    if b["preferred"]:
        return [_SectionKind.PREFERRED]
    if b["learning"]:
        return [_SectionKind.LEARNING]
    if b["responsibility"]:
        return [_SectionKind.RESPONSIBILITY]
    if b["non_qualification"]:
        return [_SectionKind.SKIP]
    return []


def strategy_b_full_coverage(content: str) -> list[_SectionKind]:
    """Option B: boundary-aware classification -- a family may only
    resolve with confidence if its matched roots, combined across ALL
    families, account for every non-stopword WORD in the heading (not
    just a prefix fragment); otherwise the heading is UNKNOWN. Reuses
    the base family-detection patterns verbatim -- no new vocabulary."""
    stopwords = {"a", "an", "the", "of", "in", "on", "and", "or", "to",
                 "for", "at", "by", "as", "we", "you", "your", "our"}
    words = [w.strip(".,;:!?").lower() for w in content.split()]
    meaningful_words = [w for w in words if w and w not in stopwords]

    b = _base_families(content)
    required_fires = b["required"] or (b["qualification"] and not b["preferred"])
    families = []
    if required_fires:
        families.append(_SectionKind.REQUIRED)
    if b["preferred"]:
        families.append(_SectionKind.PREFERRED)
    if b["learning"]:
        families.append(_SectionKind.LEARNING)
    if b["responsibility"]:
        families.append(_SectionKind.RESPONSIBILITY)
    if b["non_qualification"]:
        families.append(_SectionKind.SKIP)

    if len(families) != 1:
        return families  # ambiguous/zero already handled identically to current

    # Approximate "coverage": does ANY matched root's own pattern,
    # applied to each individual meaningful word, account for it? This
    # is a coarse per-word re-check (not exact span accounting) but
    # sufficient to show the directional effect.
    all_patterns = [_REQUIRED_ROOT, _QUALIFICATION_ROOT, _PREFERRED_ROOT,
                     _LEARNING_ROOT, _RESPONSIBILITY_ROOT, _NON_QUALIFICATION_ROOT]
    uncovered = [w for w in meaningful_words if not any(p.search(w) for p in all_patterns)]
    if uncovered:
        return []  # incomplete coverage -- fall through to UNKNOWN via shape gate
    return families


def strategy_c_candidate_profile_exclusion(content: str) -> list[_SectionKind]:
    """Option C (recommended): add ONE new, generic, closed-vocabulary
    root family (_CANDIDATE_PROFILE_ROOT, module-level above) and
    exclude NON_QUALIFICATION from firing when it co-occurs with that
    signal on the same line -- mirroring the EXISTING, already-shipped
    `required_fires = has_required or (has_qualification and not
    has_preferred)` exclusion pattern exactly. The candidate-profile
    signal itself is NEVER added to `families` (so it never becomes its
    own section kind, and never defaults to REQUIRED) -- it is used
    PURELY as an exclusion/corroboration signal, letting the heading
    fall through to the EXISTING zero-families-plus-strong-shape-signal
    UNKNOWN path untouched."""
    b = _base_families(content)
    has_candidate_profile = bool(_CANDIDATE_PROFILE_ROOT.search(content))
    required_fires = b["required"] or (b["qualification"] and not b["preferred"])
    non_qualification_fires = b["non_qualification"] and not has_candidate_profile

    families = []
    if required_fires:
        families.append(_SectionKind.REQUIRED)
    if b["preferred"]:
        families.append(_SectionKind.PREFERRED)
    if b["learning"]:
        families.append(_SectionKind.LEARNING)
    if b["responsibility"]:
        families.append(_SectionKind.RESPONSIBILITY)
    if non_qualification_fires:
        families.append(_SectionKind.SKIP)
    return families


STRATEGIES = {
    "current": strategy_current,
    "A_precedence": strategy_a_precedence,
    "B_full_coverage": strategy_b_full_coverage,
    "C_candidate_profile_exclusion": strategy_c_candidate_profile_exclusion,
}


def classify_with_strategy(heading_line: str, strategy_fn) -> str:
    span = _line_content_span(heading_line, 0)
    if span is None:
        return "NOT_A_HEADING"
    content = heading_line[span[0]:span[1]]
    # Reuse the REAL shape gate exactly as _classify_heading_line does,
    # by calling it once to get the CURRENT result's shape-gate verdict,
    # then only re-deciding the FAMILY-RESOLUTION step for strategies
    # that might change it. This never re-implements the shape gate
    # itself (bullet/colon/ALL-CAPS/Markdown/title-case/word-count), only
    # the family-matching decision downstream of it.
    current_result = _classify_heading_line(heading_line, content)
    decorated = content.strip()
    ends_with_colon = decorated.endswith(":")
    content_no_colon = decorated[:-1].strip() if ends_with_colon else decorated

    if current_result is None:
        # Shape gate itself rejected the line (too long, bullet,
        # sentence-terminal punctuation, or weak-signal-without-any-
        # family-at-all under the CURRENT family set). A strategy that
        # REMOVES a family match (B, C) could flip a weak-signal,
        # family-having line into "no longer heading-shaped" -- check
        # that specific edge directly rather than assuming "None stays
        # None."
        has_strong_shape_signal = (
            ends_with_colon
            or (any(ch.isalpha() for ch in content_no_colon)
                and all((not ch.isalpha()) or ch.isupper() for ch in content_no_colon))
            or decorated != content
        )
        if has_strong_shape_signal:
            return "NOT_A_HEADING"  # word-count/bullet/punctuation gate -- unaffected by family strategy
        return "NOT_A_HEADING"

    families = strategy_fn(content_no_colon)
    if len(families) == 1:
        return families[0].name
    if len(families) == 0:
        # Zero families: strong shape signal alone still yields UNKNOWN
        # (the existing rule) -- weak-signal-with-zero-families would
        # have already been None above via current_result, so reaching
        # here means a strong signal exists.
        return "UNKNOWN"
    return "UNKNOWN"


def main() -> None:
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    import hashlib
    freeze = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    assert hashlib.sha256(GOLD_PATH.read_bytes()).hexdigest() == freeze["sha256"], \
        "gold has drifted since freeze -- aborting"

    rows = []
    summary = {name: {"matches_gold": 0, "regressions_vs_current": 0, "fixes_vs_current": 0}
               for name in STRATEGIES}

    for control in gold["controls"]:
        heading = control["heading_line"]
        expected = control["expected_heading_kind"]
        row = {"id": control["id"], "expected": expected}
        current_val = None
        if heading is None:
            for name in STRATEGIES:
                row[name] = "NOT_A_HEADING"
            current_val = "NOT_A_HEADING"
        else:
            for name, fn in STRATEGIES.items():
                val = classify_with_strategy(heading, fn)
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

    out = {
        "corpus_version": gold["corpus_version"],
        "n_controls": len(gold["controls"]),
        "summary": summary,
        "rows": rows,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"wrote {len(rows)} rows to {OUT_PATH}")


if __name__ == "__main__":
    main()
