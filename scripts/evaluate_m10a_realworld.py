"""Milestone 10A -- real-world job-posting parsing-failure measurement.

Evaluation-only, additive, read-only against production code. Loads
`evaluation/m10/corpus.json` (two real job postings, independently
annotated BEFORE this script was written -- see that file's own
`source_note`), runs each posting's full raw text through the real,
UNMODIFIED `parse_job_description_with_diagnostics()`, and reports four
counts the Milestone 10A brief explicitly asked to measure:

1. false_positive_requirements -- a row produced where the corpus
   annotation says `is_requirement: false` (company info, learning
   narrative, legal/administrative text, or a responsibility statement,
   rendered as a scored, necessity-bearing requirement anyway).
2. invisible_genuine_qualifications / invisible_responsibilities_or_duties
   -- deliberately TWO SEPARATE, never-summed counts (a verification
   instruction after this milestone's first draft: do not inflate a
   requirement-RECALL metric by treating a job duty as an applicant
   qualification). The first counts a corpus entry with
   `is_requirement: true` (a genuine candidate qualification) for which
   NEITHER a `JobRequirement` row NOR an `UnparsedClaim` appears at all.
   The second counts a `category_annotation: "responsibilities"` entry
   (explicitly `is_requirement: false` -- a job DUTY, never scoreable)
   with the same zero-trace outcome -- diagnostic-worthy, but never a
   missed qualification. Both are strictly worse than the already-
   disclosed M9B silent-drop gap, which always leaves an `UnparsedClaim`.
3. malformed_alternative_groups -- an alternative-group row whose
   `alternative_concept_ids` contains an `unresolved:<term>` entry this
   script's own annotation did not list as a real technology for that
   claim (a fabricated extra "option"), OR a claim annotated as a
   genuine ANY-of-N group that instead produced N independent
   single-concept rows (losing OR semantics entirely).
4. correctly_preserved -- a corpus entry whose live result matches
   either its `ideal_outcome` or its `acceptable_fallback` exactly.

Writes `evaluation/reports/m10a_realworld_report.json` -- a NEW report
file; never touches any `m9b_*`/`8c:v1`/`8c:v1.1` committed report.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gitscore.jobs import parse_job_description_with_diagnostics  # noqa: E402

CORPUS_PATH = REPO_ROOT / "evaluation" / "m10" / "corpus.json"
REPORT_PATH = REPO_ROOT / "evaluation" / "reports" / "m10a_realworld_report.json"


def _load_corpus() -> dict:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def _row_for(requirements, claim_text: str):
    return [r for r in requirements if r.original_text == claim_text]


def _unparsed_for(unparsed_claims, claim_text: str):
    return [c for c in unparsed_claims if c.text == claim_text]


def _classify_claim(entry: dict, rows: list, unparsed: list) -> dict:
    is_requirement = entry["is_requirement"]
    ideal = entry.get("ideal_outcome")
    fallback = entry.get("acceptable_fallback")
    has_row = bool(rows)
    has_unparsed = bool(unparsed)

    verdict = {
        "id": entry["id"],
        "is_requirement": is_requirement,
        "has_row": has_row,
        "has_unparsed_claim": has_unparsed,
        "row_necessity": [r.necessity.value for r in rows] if has_row else [],
        "row_concept_ids": [r.concept_id for r in rows] if has_row else [],
        "row_alternative_ids": [list(r.alternative_concept_ids) for r in rows] if has_row else [],
        "false_positive_requirement": False,
        # Milestone 10A verification turn: deliberately split into two
        # NEVER-merged counts, per the explicit instruction not to
        # inflate requirement-recall metrics by treating a job DUTY/
        # responsibility as an applicant QUALIFICATION. A claim this
        # corpus annotated `is_requirement: true` (a genuine candidate
        # qualification) and a claim annotated `is_requirement: false`
        # with `category_annotation: "responsibilities"` (a job duty,
        # diagnostic-worthy but never scoreable) are different kinds of
        # content disappearing for different reasons -- reported
        # separately, summed nowhere.
        "invisible_genuine_qualification": False,
        "invisible_responsibility_or_duty": False,
        "malformed_alternative_group": False,
        "meets_ideal": False,
        "meets_fallback": False,
    }

    if not is_requirement and has_row:
        verdict["false_positive_requirement"] = True

    zero_trace = not has_row and not has_unparsed
    if zero_trace:
        if is_requirement:
            verdict["invisible_genuine_qualification"] = True
        elif entry.get("category_annotation") == "responsibilities":
            verdict["invisible_responsibility_or_duty"] = True
        # Any OTHER is_requirement=False claim with zero trace (company
        # info, legal/administrative, a heading) is counted nowhere --
        # for those, zero trace is correct behavior, not a defect; see
        # the "no_requirement_row" vs "no_scored_requirement" distinction
        # in meets_ideal below.

    if is_requirement and ideal is not None and ideal.get("type") == "alternative_group":
        expected_ids = set(ideal.get("alternative_concept_ids", []))
        if has_row and rows[0].alternative_concept_ids:
            actual_ids = set(rows[0].alternative_concept_ids)
            fabricated = {c for c in actual_ids if c.startswith("unresolved:") and c not in expected_ids}
            if fabricated:
                verdict["malformed_alternative_group"] = True
            if actual_ids == expected_ids:
                verdict["meets_ideal"] = True
        elif len(rows) > 1 and all(not r.is_alternative_group for r in rows):
            # N independent single-concept rows instead of ONE alternative group --
            # OR semantics lost entirely.
            verdict["malformed_alternative_group"] = True

    elif is_requirement and ideal is not None and ideal.get("type") in (
        "non_technical_placeholder",
        "competency_placeholder",
    ):
        # A real row exists, is correctly NOT_ASSESSABLE (concept_id=None,
        # not an alternative group), with the exact category/necessity
        # this entry's independent annotation expects.
        verdict["meets_ideal"] = (
            has_row
            and rows[0].concept_id is None
            and not rows[0].is_alternative_group
            and rows[0].category == ideal.get("category")
            and rows[0].necessity.value == ideal.get("necessity")
        )

    elif not is_requirement:
        if ideal is not None and ideal.get("type") == "no_scored_requirement":
            # Correctly never scored AND leaves a trace -- both required.
            verdict["meets_ideal"] = not has_row and has_unparsed
        else:
            verdict["meets_ideal"] = not has_row
    elif ideal is not None and ideal.get("type") in ("heading_recognized_not_a_claim",):
        verdict["meets_ideal"] = not has_row and not has_unparsed

    if fallback is not None:
        if fallback.get("type") == "unparsed_claim":
            verdict["meets_fallback"] = has_unparsed and not has_row
        elif fallback.get("type") in ("unresolved_requirement_placeholder",):
            verdict["meets_fallback"] = has_row and rows[0].concept_id is None and not verdict["malformed_alternative_group"]

    return verdict


def evaluate_posting(posting: dict) -> dict:
    source_path = REPO_ROOT / posting["source_file"]
    text = source_path.read_text(encoding="utf-8-sig")
    result = parse_job_description_with_diagnostics(text, title=posting.get("role_title"))

    verdicts = []
    for entry in posting["claims"]:
        rows = _row_for(result.profile.requirements, entry["text"])
        unparsed = _unparsed_for(result.unparsed_claims, entry["text"])
        verdicts.append(_classify_claim(entry, rows, unparsed))

    return {
        "posting_id": posting["id"],
        "claim_count": len(verdicts),
        "false_positive_requirements": sum(1 for v in verdicts if v["false_positive_requirement"]),
        "invisible_genuine_qualifications": sum(1 for v in verdicts if v["invisible_genuine_qualification"]),
        "invisible_responsibilities_or_duties": sum(1 for v in verdicts if v["invisible_responsibility_or_duty"]),
        "malformed_alternative_groups": sum(1 for v in verdicts if v["malformed_alternative_group"]),
        "meets_ideal_count": sum(1 for v in verdicts if v["meets_ideal"]),
        "meets_fallback_only_count": sum(1 for v in verdicts if v["meets_fallback"] and not v["meets_ideal"]),
        "neither_ideal_nor_fallback": [
            v["id"] for v in verdicts if not v["meets_ideal"] and not v["meets_fallback"]
        ],
        "verdicts": verdicts,
    }


def main() -> int:
    corpus = _load_corpus()
    report = {
        "corpus_version": corpus["corpus_version"],
        "postings": [evaluate_posting(p) for p in corpus["postings"]],
    }

    for posting_report in report["postings"]:
        print(f"=== {posting_report['posting_id']} ===")
        print(f"  claims annotated: {posting_report['claim_count']}")
        print(f"  false positive requirements: {posting_report['false_positive_requirements']}")
        print(f"  invisible genuine QUALIFICATIONS (zero trace): {posting_report['invisible_genuine_qualifications']}")
        print(f"  invisible RESPONSIBILITIES/duties (zero trace, never a qualification): {posting_report['invisible_responsibilities_or_duties']}")
        print(f"  malformed alternative groups: {posting_report['malformed_alternative_groups']}")
        print(f"  meets ideal_outcome: {posting_report['meets_ideal_count']} / {posting_report['claim_count']}")
        print(f"  meets acceptable_fallback (not ideal): {posting_report['meets_fallback_only_count']}")
        print(f"  meets neither: {posting_report['neither_ideal_nor_fallback']}")
        print()

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
