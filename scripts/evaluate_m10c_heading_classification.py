"""Milestone 10C Phase 2/3 -- heading-classification benchmark.

Evaluation-only, additive, read-only against production code. Loads
`evaluation/m10c/heading_controls.json` (independently annotated, written
BEFORE any candidate classifier in `scripts/evaluation_lib/heading_classifiers.py`
existed -- see that file's own `annotation_honesty_note`) and runs every
control's `text` field through all three candidate designs (A/B/C), never
through `src/gitscore`'s real, unmodified `segment_description()` -- this
milestone does not propose changing that function yet.

For each (control, strategy) pair the predicted `(is_heading, section)` is
compared against the control's annotated truth using a THREE-TIER outcome
(never a flat pass/fail), mirroring this project's M10B precedent of never
reducing "preserved as an honest diagnostic" and "wrong" to the same bucket:

- `exact_match` -- predicted outcome equals the primary annotated truth
  (or, for an `ambiguous` control, is in its `acceptable_sections`, or is
  itself `AMBIGUOUS` with a candidate set overlapping the control's own
  `acceptable_sections`).
- `safe_disagreement` -- predicted outcome differs from the primary truth
  but never fabricates unwarranted scoring-relevant confidence: predicting
  `UNKNOWN`/`AMBIGUOUS` for an entry whose truth was a specific family, or
  predicting "not a heading" for a genuinely ambiguous bare list lead-in,
  or vice versa in either of those same safe directions.
- `unsafe_mismatch` -- predicted outcome confidently assigns a named,
  scoring-relevant family (REQUIRED/PREFERRED/RESPONSIBILITY/LEARNING/
  NON_QUALIFICATION) that contradicts the annotated truth, or confidently
  calls non-heading content a heading of a named family.

Also separately reports, for traceability back to Phase 1 (never mixed
into the corpus-based precision/recall numbers): how each strategy would
classify the actual heading lines transcribed from the real SOTI and
Manulife postings (`evaluation/m10/source/*.txt`), against the same
section-family truth `evaluation/m10/corpus.json`'s own section structure
already implies.

Writes `evaluation/reports/m10c_heading_classification_report.json` and
`.md` -- NEW report files; never touches any `m10a_*`/`m10b_*`/`m9b_*`/
`8c:v1`/`8c:v1.1` committed report.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from evaluation_lib.heading_classifiers import STRATEGIES, HeadingCall  # noqa: E402

CORPUS_PATH = REPO_ROOT / "evaluation" / "m10c" / "heading_controls.json"
REPORT_JSON_PATH = REPO_ROOT / "evaluation" / "reports" / "m10c_heading_classification_report.json"
REPORT_MD_PATH = REPO_ROOT / "evaluation" / "reports" / "m10c_heading_classification_report.md"

SECTION_VALUES = ("REQUIRED", "PREFERRED", "RESPONSIBILITY", "LEARNING", "NON_QUALIFICATION", "UNKNOWN")
SCORING_RELEVANT = ("REQUIRED", "PREFERRED")  # families whose fabrication directly affects alignment_score

# Real heading lines transcribed from the two M10A source postings, with
# the section family each line's surrounding document structure implies
# (cross-checked against `evaluation/m10/corpus.json`'s own section
# narrative for each posting -- NOT derived from any candidate classifier
# output). "UNKNOWN" here means "generic intro/no clean family," not "the
# classifier failed."
REAL_POSTING_HEADINGS: tuple[tuple[str, str, str], ...] = (
    ("soti", "Opportunity", "UNKNOWN"),
    ("soti", "What you will learn:", "LEARNING"),
    ("soti", "Required skills:", "REQUIRED"),
    ("soti", "About SOTI", "NON_QUALIFICATION"),
    ("manulife", "Position Responsibilities:", "RESPONSIBILITY"),
    ("manulife", "Required Qualifications:", "REQUIRED"),
    ("manulife", "Preferred Qualifications:", "PREFERRED"),
    ("manulife", "When you join our team:", "NON_QUALIFICATION"),
    ("manulife", "Application instructions:", "NON_QUALIFICATION"),
    ("manulife", "About Manulife and John Hancock", "NON_QUALIFICATION"),
    ("manulife", "Working Arrangement", "NON_QUALIFICATION"),
)

# Today's PRODUCTION recognition (jobs/parsing/segmentation.py's existing
# four tables) -- hardcoded here as plain data (not imported) purely to
# report "already recognized today?" as a point of comparison; this
# evaluation never calls production code.
TODAY_RECOGNIZED = {
    "requirements", "required qualifications", "qualifications", "minimum qualifications",
    "basic qualifications", "must have", "must haves",
    "preferred qualifications", "preferred skills", "preferred", "nice to have", "nice-to-have",
    "nice to haves", "bonus points", "bonus", "a plus",
    "responsibilities", "what you'll do", "what you will do", "the role", "duties",
    "key responsibilities",
    "benefits", "perks", "about us", "about the company", "about the team", "compensation",
    "salary", "salary range", "what we offer", "equal opportunity employer", "how to apply",
    "our values", "who we are", "why join us", "diversity", "diversity and inclusion",
    "perks and benefits",
}


def _today_recognizes(text: str) -> bool:
    normalized = text.strip().rstrip(":").strip().lower()
    return normalized in TODAY_RECOGNIZED


def _load_corpus() -> dict:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def _acceptable_set(entry: dict) -> set[str]:
    base = {entry["expected_section"]} if entry.get("expected_section") else set()
    base |= set(entry.get("acceptable_sections", []))
    return base


def _score_entry(entry: dict, call: HeadingCall) -> str:
    """Returns one of 'exact_match' / 'safe_disagreement' / 'unsafe_mismatch'."""
    truth_is_heading = entry["is_heading"]
    ambiguous = entry.get("ambiguous", False)
    acceptable = _acceptable_set(entry)

    if not truth_is_heading:
        # Ground truth: this line is NOT a real section heading at all
        # (either an ordinary sentence, or a list lead-in).
        if not call.is_heading:
            return "exact_match"
        if call.section in ("UNKNOWN", "AMBIGUOUS"):
            return "safe_disagreement"  # heading-shaped-but-unresolved never fabricates a scoring-relevant family
        return "unsafe_mismatch"  # confidently assigned a named family to non-heading content

    # Ground truth: this line IS a real section heading.
    if not call.is_heading:
        return "unsafe_mismatch" if not ambiguous else "safe_disagreement"

    if call.section == "AMBIGUOUS":
        overlap = set(call.candidates) & acceptable
        return "exact_match" if overlap else "safe_disagreement"

    if call.section in acceptable:
        return "exact_match"
    if call.section == "UNKNOWN":
        return "safe_disagreement"
    return "unsafe_mismatch"


def _confusion_and_prf(entries: list[dict], calls: dict[str, HeadingCall]) -> dict:
    """Strict precision/recall/confusion, computed ONLY over non-ambiguous,
    is_heading=true entries -- the "confident ground truth" subset. Kept
    deliberately separate from the 3-tier scoring above, which also covers
    ambiguous and non-heading entries.
    """
    confident = [e for e in entries if e["is_heading"] and not e.get("ambiguous", False)]
    per_family = {fam: {"tp": 0, "fp": 0, "fn": 0} for fam in SECTION_VALUES}
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for entry in confident:
        truth = entry["expected_section"]
        call = calls[entry["id"]]
        predicted = call.section if call.is_heading else "NOT_HEADING"
        confusion[truth][predicted] += 1
        if predicted == truth:
            per_family[truth]["tp"] += 1
        else:
            per_family[truth]["fn"] += 1
            if predicted in per_family:
                per_family[predicted]["fp"] += 1

    result = {}
    for fam, counts in per_family.items():
        tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        result[fam] = {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall}
    return {
        "per_family": result,
        "confusion_matrix": {k: dict(v) for k, v in confusion.items()},
        "confident_entry_count": len(confident),
    }


def _run_strategy(strategy_name: str, classify, entries: list[dict]) -> dict:
    calls: dict[str, HeadingCall] = {e["id"]: classify(e["text"]) for e in entries}
    tiers = defaultdict(list)
    for entry in entries:
        tier = _score_entry(entry, calls[entry["id"]])
        tiers[tier].append(entry["id"])

    unsafe_detail = []
    for entry_id in tiers["unsafe_mismatch"]:
        entry = next(e for e in entries if e["id"] == entry_id)
        call = calls[entry_id]
        truth_section = entry.get("expected_section")
        # Severity: a REQUIRED/PREFERRED row is the only kind that enters
        # assess_job()'s alignment-score denominator at all -- a mismatch
        # touching either is "high" (can fabricate or silently drop a
        # scored requirement); every other family mismatch is "low" (the
        # claim still falls through to the pre-existing, already-accepted
        # outside-section heuristic gate, same as today, see M10B 3.3).
        severity = (
            "high"
            if truth_section in SCORING_RELEVANT or call.section in SCORING_RELEVANT
            else "low"
        )
        unsafe_detail.append({
            "id": entry_id,
            "text": entry["text"],
            "truth_is_heading": entry["is_heading"],
            "truth_section": truth_section,
            "predicted_is_heading": call.is_heading,
            "predicted_section": call.section,
            "severity": severity,
        })

    heading_detection_correct = sum(
        1 for e in entries if (calls[e["id"]].is_heading == e["is_heading"])
    )

    real_posting_trace = []
    for posting, text, truth in REAL_POSTING_HEADINGS:
        call = classify(text)
        real_posting_trace.append({
            "posting": posting,
            "text": text,
            "truth_section": truth,
            "today_recognized": _today_recognizes(text),
            "predicted_is_heading": call.is_heading,
            "predicted_section": call.section,
            "candidates": list(call.candidates) if call.candidates else [],
            "matches_truth": (
                call.is_heading
                and (call.section == truth or (call.section == "AMBIGUOUS" and truth in call.candidates))
            ),
        })

    return {
        "strategy": strategy_name,
        "total_entries": len(entries),
        "heading_detection_accuracy": heading_detection_correct / len(entries),
        "outcome_tier_counts": {tier: len(ids) for tier, ids in tiers.items()},
        "outcome_tier_entry_ids": dict(tiers),
        "unsafe_mismatches": unsafe_detail,
        "strict_prf": _confusion_and_prf(entries, calls),
        "real_posting_trace": real_posting_trace,
        "real_posting_headings_correctly_classified": sum(1 for r in real_posting_trace if r["matches_truth"]),
        "real_posting_headings_total": len(real_posting_trace),
        "real_posting_headings_recognized_today": sum(1 for r in real_posting_trace if r["today_recognized"]),
    }


def main() -> None:
    corpus = _load_corpus()
    entries = corpus["controls"]

    report = {
        "corpus_path": str(CORPUS_PATH.relative_to(REPO_ROOT)),
        "corpus_entry_count": len(entries),
        "strategies": {},
    }
    for name, classify in STRATEGIES.items():
        report["strategies"][name] = _run_strategy(name, classify, entries)

    REPORT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    REPORT_MD_PATH.write_text(_render_markdown(report), encoding="utf-8")
    print(f"Wrote {REPORT_JSON_PATH}")
    print(f"Wrote {REPORT_MD_PATH}")


def _render_markdown(report: dict) -> str:
    lines = [
        "# Milestone 10C Heading Classification Report",
        "",
        f"Corpus: `{report['corpus_path']}` -- {report['corpus_entry_count']} entries.",
        "",
        "## Summary",
        "",
        "| Strategy | Heading-detection accuracy | exact_match | safe_disagreement | unsafe_mismatch | Real-posting headings correct (of 11) |",
        "|---|---|---|---|---|---|",
    ]
    for name, data in report["strategies"].items():
        tiers = data["outcome_tier_counts"]
        lines.append(
            f"| {name} | {data['heading_detection_accuracy']:.3f} | "
            f"{tiers.get('exact_match', 0)} | {tiers.get('safe_disagreement', 0)} | "
            f"{tiers.get('unsafe_mismatch', 0)} | "
            f"{data['real_posting_headings_correctly_classified']} |"
        )

    for name, data in report["strategies"].items():
        lines.append("")
        lines.append(f"## {name}")
        lines.append("")
        lines.append("### Strict per-family precision/recall (non-ambiguous, is_heading=true entries only)")
        lines.append("")
        lines.append("| Family | TP | FP | FN | Precision | Recall |")
        lines.append("|---|---|---|---|---|---|")
        for fam, m in data["strict_prf"]["per_family"].items():
            prec = f"{m['precision']:.3f}" if m["precision"] is not None else "n/a"
            rec = f"{m['recall']:.3f}" if m["recall"] is not None else "n/a"
            lines.append(f"| {fam} | {m['tp']} | {m['fp']} | {m['fn']} | {prec} | {rec} |")

        if data["unsafe_mismatches"]:
            lines.append("")
            lines.append("### Unsafe mismatches (confidently wrong, scoring-relevant)")
            lines.append("")
            lines.append("| id | text | truth | predicted | severity |")
            lines.append("|---|---|---|---|---|")
            for um in data["unsafe_mismatches"]:
                truth = "NOT_HEADING" if not um["truth_is_heading"] else um["truth_section"]
                predicted = "NOT_HEADING" if not um["predicted_is_heading"] else um["predicted_section"]
                lines.append(f"| {um['id']} | {um['text'][:60]} | {truth} | {predicted} | {um['severity']} |")

        lines.append("")
        lines.append("### Real-posting heading trace")
        lines.append("")
        lines.append("| posting | text | truth | today recognized? | predicted | matches truth? |")
        lines.append("|---|---|---|---|---|---|")
        for r in data["real_posting_trace"]:
            predicted = r["predicted_section"] if r["predicted_is_heading"] else "NOT_HEADING"
            lines.append(
                f"| {r['posting']} | {r['text']} | {r['truth_section']} | "
                f"{r['today_recognized']} | {predicted} | {r['matches_truth']} |"
            )

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
