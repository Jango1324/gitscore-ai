"""Milestone 11-F Phase 1 -- metric-integrity audit of M11-E's own
reporting methodology.

Evaluation-only, additive, read-only against production code AND
against M11-E's own frozen corpus/report -- no extraction algorithm,
no gold annotation, is modified by this script.

M11-E's own `evaluate_m11e_v2_extractor.py` computed tag precision as
`tag_tp / (tag_tp + fp_related_unknown)`, where `tag_tp` counts a
CONTROL as correct the moment its expected tag appears ANYWHERE among
the tags produced for it -- so a control where the extractor also
emits one extra, unexpected tag (`m11e-multi-02`: expected
{embedded-systems-design, digital-logic}, produced {embedded-systems-
design, digital-logic, system-design}) was counted as a full "hit"
with the extra tag tracked only in a SEPARATE
`unexpected_additional_tag_count` field, never folded into the
precision denominator itself. That is a CONTROL-level ("did this
sentence get at least its right tag") framing, not a PREDICTION-level
one -- and, as this milestone's own instruction points out, mixing the
two make "64/64 precision, 1 unexpected tag" read as if nothing were
wrong, when a standard per-prediction precision score is measurably
lower.

This script recomputes EVERY tag-level metric at the PREDICTION level
(treating each `Qualification.normalized_reference.competency_tag`
the extractor actually emits for a control as one prediction, compared
against the FULL set of tags that control's own `expected_competency_tag`
+ `sibling_tags` fields say should appear) and reports the
corrected numbers side by side with M11-E's own originals -- nothing
in `evaluation/m11e/paraphrase_development_controls.json` or
`competency_extraction.py` is touched.

Writes `evaluation/reports/m11f_metric_reconciliation_report.json`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gitscore.jobs.models import SourceSpan  # noqa: E402
from gitscore.jobs.parsing.competency_extraction import (  # noqa: E402
    DeclinedExtraction,
    extract_competency_qualifications,
    extract_competency_qualifications_v2,
)

CORPUS_PATH = REPO_ROOT / "evaluation" / "m11e" / "paraphrase_development_controls.json"
REPORT_PATH = REPO_ROOT / "evaluation" / "reports" / "m11f_metric_reconciliation_report.json"


def _expected_tags(control: dict) -> frozenset[str]:
    """The FULL set of tags a correct extraction should produce for
    this control -- the primary `expected_competency_tag` plus any
    `sibling_tags` (both already present in the corpus's own schema,
    unchanged). Empty for every control where no SPECIFIC tag should
    ever be asserted: `related_only`/`unknown` (must never auto-map,
    Phase 3's own contract), and the two structural shapes
    (`or_any` -- `missing_contract`, correctly declines entirely;
    `mixed_unsupported` -- correctly produces a real `Qualification`
    with NO tag at all, `normalized_reference=None`)."""
    tag = control.get("expected_competency_tag")
    tags = set(control.get("sibling_tags", []))
    if tag:
        tags.add(tag)
    return frozenset(tags)


def _predicted_tags(result) -> frozenset[str]:
    if isinstance(result, DeclinedExtraction):
        return frozenset()
    return frozenset(q.normalized_reference.competency_tag for q in result if q.normalized_reference is not None)


def _is_positive(result) -> bool:
    return not isinstance(result, DeclinedExtraction)


def _evaluate(extractor, controls: list[dict]) -> dict:
    tp = fp = fn = 0
    exact_set_matches = exact_set_total = 0
    per_control: list[dict] = []

    # Qualification-level coverage: ALL 82 genuinely-true-qualification
    # controls, regardless of category (named_technology/education/
    # uninterpretable included -- explicitly OUT OF v2's own scope, but
    # still part of this honest denominator, exactly as M11-E's own
    # "qualification recall" already counted them).
    qual_tp = qual_total = 0

    # Conservative-decline breakdown, scoped consistently over ALL 92
    # controls (not just technical_competency) so the sub-counts always
    # sum back to the total -- a control that declined is bucketed into
    # exactly one of three mutually exclusive outcomes:
    #   - safety_correct_decline: not a qualification at all (negation,
    #     narrative, responsibility-lead, or a genuinely out-of-taxonomy
    #     claim) -- declining is the intended, correct behavior.
    #   - out_of_scope_decline: IS a genuine qualification, but outside
    #     v2's own tag taxonomy by design (named_technology/education),
    #     or a related_only/unknown competency claim that must never be
    #     auto-mapped to a specific tag -- a conservative abstention,
    #     not a bug.
    #   - missed_tag_decline: IS a technical_competency qualification
    #     with a specific expected tag (or tag set) that the extractor
    #     simply failed to recognize -- a real miss.
    declines_safety_correct = 0
    declines_out_of_scope = 0
    declines_missed_tag = 0
    declines_total = 0
    # False accepts at the qualification level: extractor produced
    # something for text that is NOT an applicant qualification at all.
    # Expected to be zero given v1/v2's own safety-filter design --
    # tracked explicitly rather than assumed.
    false_accepts_non_qualification = 0

    for control in controls:
        text = control["text"]
        span = SourceSpan(0, len(text))
        result = extractor(text, span)
        positive = _is_positive(result)
        is_qual = control["is_applicant_qualification"]
        expected = _expected_tags(control)

        if is_qual:
            qual_total += 1
            if positive:
                qual_tp += 1
        elif positive:
            false_accepts_non_qualification += 1

        if not positive:
            declines_total += 1
            if not is_qual:
                declines_safety_correct += 1
            elif control["text_category"] != "technical_competency" or expected == frozenset():
                declines_out_of_scope += 1
            else:
                declines_missed_tag += 1

        if control["text_category"] != "technical_competency":
            continue

        predicted = _predicted_tags(result)

        control_tp = len(expected & predicted)
        control_fp = len(predicted - expected)
        control_fn = len(expected - predicted)
        tp += control_tp
        fp += control_fp
        fn += control_fn

        exact_set_total += 1
        is_exact = predicted == expected
        if is_exact:
            exact_set_matches += 1

        per_control.append({
            "id": control["id"],
            "expected_tags": sorted(expected),
            "predicted_tags": sorted(predicted),
            "control_tp": control_tp,
            "control_fp": control_fp,
            "control_fn": control_fn,
            "exact_set_match": is_exact,
        })

    return {
        "tag_level_prediction_metrics": {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": {"numerator": tp, "denominator": tp + fp},
            "recall": {"numerator": tp, "denominator": tp + fn},
        },
        "exact_set_accuracy": {"numerator": exact_set_matches, "denominator": exact_set_total},
        "qualification_extraction_coverage": {"numerator": qual_tp, "denominator": qual_total},
        "false_accepts_non_qualification": false_accepts_non_qualification,
        "conservative_declines": {
            "total": declines_total,
            "safety_correct_decline": declines_safety_correct,
            "out_of_scope_decline": declines_out_of_scope,
            "missed_tag_decline": declines_missed_tag,
        },
        "per_control": per_control,
    }


def main() -> None:
    controls = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))["controls"]
    v1 = _evaluate(extract_competency_qualifications, controls)
    v2 = _evaluate(extract_competency_qualifications_v2, controls)

    report = {
        "methodology_note": (
            "Corrects M11-E's own control-level tag precision/recall framing to a standard "
            "PREDICTION-level one: every (control, tag) pair is counted individually as a true "
            "positive, false positive, or false negative, rather than a control being scored as "
            "a full 'hit' the moment its expected tag appears anywhere among the tags produced. "
            "Neither competency_extraction.py nor paraphrase_development_controls.json is modified "
            "by this script -- this is a reporting-only correction."
        ),
        "v1_m11c": v1,
        "v2_m11e": v2,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    for label, r in (("v1 (M11-C)", v1), ("v2 (M11-E)", v2)):
        print(f"=== {label} ===")
        m = r["tag_level_prediction_metrics"]
        print(f"  TP={m['true_positives']} FP={m['false_positives']} FN={m['false_negatives']}")
        print(f"  precision: {m['precision']['numerator']}/{m['precision']['denominator']}")
        print(f"  recall:    {m['recall']['numerator']}/{m['recall']['denominator']}")
        e = r["exact_set_accuracy"]
        print(f"  exact-set accuracy: {e['numerator']}/{e['denominator']}")
        q = r["qualification_extraction_coverage"]
        print(f"  qualification extraction coverage: {q['numerator']}/{q['denominator']}")
        print(f"  false accepts (non-qualification text): {r['false_accepts_non_qualification']}")
        print(f"  conservative declines: {r['conservative_declines']}")
        print()
    print(f"Wrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
