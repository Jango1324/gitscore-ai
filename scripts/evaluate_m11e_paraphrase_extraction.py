"""Milestone 11-E Phase 3 -- paraphrase-matching strategy comparison.

Evaluation-only, additive, read-only against production code. Loads
`evaluation/m11e/paraphrase_development_controls.json` (92 independently
annotated examples, authored BEFORE this script was written), applies
the EXISTING, unmodified M11-C sentence-role rejection filters
(negation / narrative / responsibility, imported directly from
`competency_extraction.py`, never re-derived) first, then runs all
three Phase 3 candidate tag-matching strategies
(`scripts/evaluation_lib/m11e_paraphrase_prototypes.py`) against every
remaining control, and reports EXACT numerator/denominator counts.

Writes `evaluation/reports/m11e_paraphrase_extraction_report.json`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from evaluation_lib.m11e_paraphrase_prototypes import STRATEGIES  # noqa: E402

from gitscore.jobs.parsing.competency_extraction import (  # noqa: E402
    _BROADER_NARRATIVE_SUBJECT,
    _NEGATION_PATTERNS,
    _RESPONSIBILITY_LEAD,
)
from gitscore.jobs.parsing.narrative import contains_narrative_cue  # noqa: E402

CORPUS_PATH = REPO_ROOT / "evaluation" / "m11e" / "paraphrase_development_controls.json"
REPORT_PATH = REPO_ROOT / "evaluation" / "reports" / "m11e_paraphrase_extraction_report.json"


def _sentence_role_rejected(text: str) -> bool:
    """The EXISTING, unmodified M11-C sentence-role rejection filters --
    reused directly, never re-derived, so this comparison measures ONLY
    the tag-matching layer each strategy proposes, not sentence-role
    handling (already solved, M11-C/M11-D confirmed this piece works)."""
    if any(p.search(text) for p in _NEGATION_PATTERNS):
        return True
    if contains_narrative_cue(text) or _BROADER_NARRATIVE_SUBJECT.search(text):
        return True
    if _RESPONSIBILITY_LEAD.match(text.strip()):
        return True
    return False


def _load_corpus() -> list[dict]:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))["controls"]


def _evaluate_strategy(name: str, match_fn, controls: list[dict]) -> dict:
    tp_correct_tag = tp_wrong_tag = fn = 0
    fp_related_unknown = 0  # fired on a RELATED_ONLY/UNKNOWN control at all
    related_unknown_total = 0
    correct_relation_sensitivity = relation_sensitivity_total = 0
    structural_total = structural_correctly_undetermined = 0
    mismatches: list[dict] = []

    for control in controls:
        text = control["text"]
        if _sentence_role_rejected(text):
            continue  # out of scope for this layer -- already handled upstream, identically for every strategy

        matches = match_fn(text)
        expected_tag = control.get("expected_competency_tag")
        expected_relation = control.get("expected_match_relation")

        if control["text_category"] != "technical_competency":
            if matches:
                mismatches.append({"id": control["id"], "strategy": name, "error": "false_positive_non_competency"})
            continue

        if control.get("logical_composition") in ("or_any", "mixed_unsupported") and expected_tag is None:
            # Tests LOGICAL-STRUCTURE handling (M11-C's own disclosed
            # missing-contract/MIXED_UNSUPPORTED shapes), not tag-matching
            # -- a separate, already-scoped concern; bucketed apart from
            # plain recall/precision rather than conflated with it.
            structural_total += 1
            # A strategy "correctly" leaves this undetermined for THIS
            # layer's own purposes if it does not confidently resolve to
            # exactly one tag with no ambiguity -- multiple tags firing
            # (as every strategy's own canonical/alias matches legitimately
            # would, since the sentence really does mention several
            # areas) is the HONEST signal Phase 4's real implementation
            # must route to a safe decline, not a defect at this layer.
            if len({t for t, _r in matches}) != 1:
                structural_correctly_undetermined += 1
            else:
                mismatches.append({"id": control["id"], "strategy": name, "error": "structural_case_resolved_to_single_tag", "tags": sorted({t for t, _r in matches})})
            continue

        if expected_relation in ("related_only", "unknown"):
            related_unknown_total += 1
            fired_tags = {t for t, _r in matches}
            if fired_tags:
                fp_related_unknown += 1
                mismatches.append({"id": control["id"], "strategy": name, "error": "false_positive_related_or_unknown", "fired_tags": sorted(fired_tags)})
            continue

        matched_entry = next((m for m in matches if m[0] == expected_tag), None)
        if matched_entry is None:
            fn += 1
            mismatches.append({"id": control["id"], "strategy": name, "error": "false_negative"})
            continue

        tp_correct_tag += 1
        relation_sensitivity_total += 1
        _tag, found_relation = matched_entry
        # Canonical-phrase hits are reported as SEMANTICALLY_EQUIVALENT
        # by every strategy's own matcher (see each match_option_* docstring);
        # treat "canonical" ground truth as satisfied by either label.
        if expected_relation == "canonical" or found_relation.value == expected_relation:
            correct_relation_sensitivity += 1
        else:
            mismatches.append({"id": control["id"], "strategy": name, "error": "relation_label_mismatch", "expected": expected_relation, "actual": found_relation.value})

        wrong_sibling_tags = {t for t, _r in matches if t != expected_tag}
        if wrong_sibling_tags - set(control.get("sibling_tags", [])):
            tp_wrong_tag += 1
            mismatches.append({"id": control["id"], "strategy": name, "error": "unexpected_additional_tag", "tags": sorted(wrong_sibling_tags)})

    return {
        "strategy": name,
        "recall": {"numerator": tp_correct_tag, "denominator": tp_correct_tag + fn},
        "precision_related_unknown_rejection": {
            "numerator": related_unknown_total - fp_related_unknown,
            "denominator": related_unknown_total,
        },
        "relation_label_sensitivity": {"numerator": correct_relation_sensitivity, "denominator": relation_sensitivity_total},
        "unexpected_additional_tag_count": tp_wrong_tag,
        "structural_cases_correctly_undetermined": {"numerator": structural_correctly_undetermined, "denominator": structural_total},
        "mismatches": mismatches,
    }


def main() -> None:
    controls = _load_corpus()
    results = {name: _evaluate_strategy(name, fn, controls) for name, fn in STRATEGIES.items()}

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")

    for name, r in results.items():
        print(f"=== {name} ===")
        print(f"  recall:                          {r['recall']['numerator']}/{r['recall']['denominator']}")
        print(f"  related/unknown correctly rejected: {r['precision_related_unknown_rejection']['numerator']}/{r['precision_related_unknown_rejection']['denominator']}")
        print(f"  relation-label sensitivity:      {r['relation_label_sensitivity']['numerator']}/{r['relation_label_sensitivity']['denominator']}")
        print(f"  unexpected additional tags:      {r['unexpected_additional_tag_count']}")
        s = r["structural_cases_correctly_undetermined"]
        print(f"  structural cases correctly left undetermined: {s['numerator']}/{s['denominator']}")
        print(f"  mismatches: {len(r['mismatches'])}")
        print()
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
