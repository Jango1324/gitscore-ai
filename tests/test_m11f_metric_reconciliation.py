"""Milestone 11-F Phase 1 -- dedicated test for the metric-integrity
reconciliation script.

Verifies the corrected, PREDICTION-level counting methodology in
`scripts/evaluate_m11f_metric_reconciliation.py` against small,
hand-constructed control sets -- not against the real M11-E corpus,
so this test does not depend on (and cannot be broken by) any future
change to `paraphrase_development_controls.json`.

Confirms, independently of the live script run:
  - a control with one correct tag and one unexpected extra tag
    contributes 1 TP and 1 FP, not a "free" full hit;
  - a multi-tag control's `sibling_tags` are folded into the expected
    set so recall is computed against the FULL expected tag set, not
    just the primary tag;
  - `conservative_declines` buckets are mutually exclusive and always
    sum back to the total;
  - `qualification_extraction_coverage` is computed over ALL
    `is_applicant_qualification=True` controls, including categories
    outside `technical_competency`.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

_SPEC = importlib.util.spec_from_file_location(
    "evaluate_m11f_metric_reconciliation",
    REPO_ROOT / "scripts" / "evaluate_m11f_metric_reconciliation.py",
)
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)  # type: ignore[union-attr]

_expected_tags = _MODULE._expected_tags
_evaluate = _MODULE._evaluate


def _control(
    id_: str,
    text: str,
    is_qual: bool,
    category: str = "technical_competency",
    expected_tag: str | None = None,
    sibling_tags: list[str] | None = None,
) -> dict:
    control = {
        "id": id_,
        "text": text,
        "is_applicant_qualification": is_qual,
        "text_category": category,
        "expected_competency_tag": expected_tag,
    }
    if sibling_tags:
        control["sibling_tags"] = sibling_tags
    return control


def test_expected_tags_folds_in_sibling_tags():
    control = _control(
        "c1", "x", True, expected_tag="database-design", sibling_tags=["system-design"]
    )
    assert _expected_tags(control) == frozenset({"database-design", "system-design"})


def test_expected_tags_empty_when_no_tag_and_no_siblings():
    control = _control("c1", "x", True, category="technical_competency", expected_tag=None)
    assert _expected_tags(control) == frozenset()


def test_unexpected_extra_tag_counts_as_false_positive_not_a_free_hit():
    """A control whose extractor finds the right tag PLUS one extra,
    unexpected tag must contribute exactly 1 TP and 1 FP -- it must
    NOT be scored as a clean "hit" with the extra tag invisible to
    precision, which is precisely the M11-E control-level framing
    this milestone's own instruction flags as misleading."""
    controls = [_control("c1", "embedded systems design and digital logic", True, expected_tag="embedded-systems-design", sibling_tags=["digital-logic"])]

    def fake_extractor(text, span):
        class _Ref:
            def __init__(self, tag):
                self.competency_tag = tag

        class _Qual:
            def __init__(self, tag):
                self.normalized_reference = _Ref(tag)

        return (_Qual("embedded-systems-design"), _Qual("digital-logic"), _Qual("system-design"))

    result = _evaluate(fake_extractor, controls)
    m = result["tag_level_prediction_metrics"]
    assert m["true_positives"] == 2
    assert m["false_positives"] == 1
    assert m["false_negatives"] == 0
    assert result["exact_set_accuracy"] == {"numerator": 0, "denominator": 1}


def test_conservative_declines_buckets_are_mutually_exclusive_and_sum_to_total():
    controls = [
        _control("neg", "x", False, category="ambiguous"),
        _control("related", "x", True, expected_tag=None),
        _control("miss", "x", True, expected_tag="concurrency"),
    ]

    def declining_extractor(text, span):
        from gitscore.jobs.parsing.competency_extraction import DeclinedExtraction

        return DeclinedExtraction(reason="test", detail="test")

    result = _evaluate(declining_extractor, controls)
    d = result["conservative_declines"]
    assert d["total"] == 3
    assert d["safety_correct_decline"] + d["out_of_scope_decline"] + d["missed_tag_decline"] == d["total"]
    assert d["safety_correct_decline"] == 1
    assert d["out_of_scope_decline"] == 1
    assert d["missed_tag_decline"] == 1


def test_qualification_extraction_coverage_includes_non_technical_competency_categories():
    controls = [
        _control("named-tech", "x", True, category="named_technology", expected_tag=None),
        _control("edu", "x", True, category="education", expected_tag=None),
    ]

    def positive_extractor(text, span):
        class _Qual:
            normalized_reference = None

        return (_Qual(),)

    result = _evaluate(positive_extractor, controls)
    assert result["qualification_extraction_coverage"] == {"numerator": 2, "denominator": 2}


def test_false_accept_tracked_when_extractor_is_positive_on_non_qualification_text():
    controls = [_control("narrative", "x", False, category="company_narrative")]

    def positive_extractor(text, span):
        class _Qual:
            normalized_reference = None

        return (_Qual(),)

    result = _evaluate(positive_extractor, controls)
    assert result["false_accepts_non_qualification"] == 1
    assert result["conservative_declines"]["total"] == 0


def test_reconciliation_against_real_frozen_m11e_corpus_and_extractors_is_internally_consistent():
    """End-to-end sanity check against the ACTUAL frozen M11-E corpus
    and the ACTUAL, unmodified v1/v2 extractors (read-only; neither is
    touched). Locks in the specific reconciled numbers so a future,
    unnoticed change to either extractor or the corpus is caught."""
    import json

    from gitscore.jobs.parsing.competency_extraction import (
        extract_competency_qualifications,
        extract_competency_qualifications_v2,
    )

    controls = json.loads(_MODULE.CORPUS_PATH.read_text(encoding="utf-8"))["controls"]

    v1 = _evaluate(extract_competency_qualifications, controls)
    v2 = _evaluate(extract_competency_qualifications_v2, controls)

    for result in (v1, v2):
        d = result["conservative_declines"]
        assert d["safety_correct_decline"] + d["out_of_scope_decline"] + d["missed_tag_decline"] == d["total"]
        m = result["tag_level_prediction_metrics"]
        assert m["precision"]["denominator"] == m["true_positives"] + m["false_positives"]
        assert m["recall"]["denominator"] == m["true_positives"] + m["false_negatives"]

    assert v2["tag_level_prediction_metrics"] == {
        "true_positives": 68,
        "false_positives": 1,
        "false_negatives": 0,
        "precision": {"numerator": 68, "denominator": 69},
        "recall": {"numerator": 68, "denominator": 68},
    }
    assert v1["tag_level_prediction_metrics"] == {
        "true_positives": 29,
        "false_positives": 0,
        "false_negatives": 39,
        "precision": {"numerator": 29, "denominator": 29},
        "recall": {"numerator": 29, "denominator": 68},
    }
    assert v2["qualification_extraction_coverage"] == {"numerator": 65, "denominator": 82}
    assert v1["qualification_extraction_coverage"] == {"numerator": 26, "denominator": 82}
    assert v2["exact_set_accuracy"] == {"numerator": 78, "denominator": 79}
    assert v1["false_accepts_non_qualification"] == 0
    assert v2["false_accepts_non_qualification"] == 0
