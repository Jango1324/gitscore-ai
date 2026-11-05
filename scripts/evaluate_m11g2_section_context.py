"""Milestone 11-G2 -- evaluate extract_competency_qualifications_v2's
section-aware qualification/necessity inference against the frozen
control corpus (`evaluation/m11g2/section_context_controls.json`,
hash-frozen in `evaluation/m11g2/controls_hash_freeze.json` BEFORE any
production or offline-extractor code was modified).

Run with --baseline to label the report as a pre-fix baseline (the
unmodified function called WITHOUT any section kwargs at all -- the
exact pre-M11-G2 calling convention), or without the flag for the
post-fix comparison (the function called WITH real section context).
Both runs hash-verify the frozen corpus first.

`direct_controls` exercise the new logic directly via a hand-specified
section_kind/document_has_recognized_heading pair. `mini_posting_controls`
run the REAL, unmodified `segment_description()` over a genuine
multi-line mini-posting first, to confirm end-to-end plumbing.

Writes evaluation/reports/m11g2_<label>_report.json.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gitscore.jobs.models import SourceSpan  # noqa: E402
from gitscore.jobs.parsing.competency_extraction import (  # noqa: E402
    DeclinedExtraction,
    extract_competency_qualifications_v2,
)
from gitscore.jobs.parsing.segmentation import (  # noqa: E402
    document_has_any_recognized_heading,
    segment_description,
)

CORPUS_PATH = REPO_ROOT / "evaluation" / "m11g2" / "section_context_controls.json"
HASH_FREEZE_PATH = REPO_ROOT / "evaluation" / "m11g2" / "controls_hash_freeze.json"


def _verify_hash_freeze() -> None:
    freeze = json.loads(HASH_FREEZE_PATH.read_text(encoding="utf-8"))
    actual = hashlib.sha256(CORPUS_PATH.read_bytes()).hexdigest()
    if actual != freeze["sha256"]:
        raise SystemExit(
            f"G2 CONTROL HASH MISMATCH: expected {freeze['sha256']}, got {actual}. "
            "Refusing to evaluate against a corpus that may have been altered after freezing."
        )


def _run_extractor(text: str, span: SourceSpan, *, section_kind, doc_heading: bool, use_section_context: bool):
    if not use_section_context:
        return extract_competency_qualifications_v2(text, span)
    return extract_competency_qualifications_v2(
        text, span,
        section_kind=section_kind,
        document_has_recognized_heading=doc_heading,
        has_section_context=True,
    )


def _check(result, expect: dict) -> tuple[bool, dict]:
    is_decline = isinstance(result, DeclinedExtraction)
    actual = {
        "declined": is_decline,
        "reason": result.reason if is_decline else None,
        "tags": None if is_decline else sorted(
            q.normalized_reference.competency_tag for q in result if q.normalized_reference is not None
        ),
        "necessity": None if is_decline else (
            result[0].necessity.value.upper() if (len(result) > 0 and result[0].necessity is not None) else None
        ),
        "applicability_condition_present": None if is_decline else any(
            q.applicability_condition is not None for q in result
        ),
    }

    expect_decline = expect.get("expect_decline", False)
    ok = actual["declined"] == expect_decline
    if ok and expect_decline:
        ok = actual["reason"] == expect.get("expect_reason")
    if ok and not expect_decline:
        expected_tag = expect.get("expect_tag")
        if expected_tag is not None:
            ok = ok and actual["tags"] == [expected_tag]
        ok = ok and actual["necessity"] == expect.get("expect_necessity")
        expected_app = expect.get("expect_applicability_present")
        if expected_app is not None:
            ok = ok and actual["applicability_condition_present"] == expected_app
    return ok, actual


def _evaluate(controls: dict, use_section_context: bool) -> dict:
    results = []
    pass_count = 0
    total = 0

    for control in controls["direct_controls"]:
        total += 1
        text = control["text"]
        span = SourceSpan(0, len(text))
        result = _run_extractor(
            text, span,
            section_kind=control["section_kind"], doc_heading=control["document_has_recognized_heading"],
            use_section_context=use_section_context,
        )
        ok, actual = _check(result, control)
        pass_count += int(ok)
        results.append({"id": control["id"], "category": control["category"], "pass": ok, "actual": actual})

    for mp in controls["mini_posting_controls"]:
        description = mp["description"]
        claims = segment_description(description)
        doc_heading = document_has_any_recognized_heading(description)
        by_text = {c.text: c for c in claims}
        for target in mp["targets"]:
            total += 1
            claim = by_text.get(target["target_text"])
            if claim is None:
                results.append({
                    "id": mp["id"], "category": mp["category"], "pass": False,
                    "actual": {"error": "target claim not found in segmentation output", "target_text": target["target_text"]},
                })
                continue
            span = SourceSpan(claim.start, claim.end)
            result = _run_extractor(
                claim.text, span,
                section_kind=claim.section_kind, doc_heading=doc_heading,
                use_section_context=use_section_context,
            )
            ok, actual = _check(result, target)
            pass_count += int(ok)
            results.append({"id": mp["id"], "category": mp["category"], "pass": ok, "actual": actual, "target_text": target["target_text"]})

    return {"pass_count": pass_count, "total": total, "failures": [r for r in results if not r["pass"]], "all_results": results}


def main() -> None:
    _verify_hash_freeze()
    label = "baseline" if "--baseline" in sys.argv else "after"
    use_section_context = label != "baseline"
    controls = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))

    result = _evaluate(controls, use_section_context)

    report = {"label": label, "use_section_context": use_section_context, "result": result}
    out_path = REPO_ROOT / "evaluation" / "reports" / f"m11g2_{label}_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=False), encoding="utf-8")

    print(f"=== {label} (use_section_context={use_section_context}) ===")
    print(f"{result['pass_count']}/{result['total']} assertions match expectation")
    if result["failures"]:
        print("failures:")
        for f in result["failures"]:
            extra = f" target={f['target_text']!r}" if "target_text" in f else ""
            print(f"  {f['id']} (cat {f['category']}){extra}: {f['actual']}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
