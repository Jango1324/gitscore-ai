"""Milestone 11-G7 Phase 1/4 -- measures the REAL, unmodified live
parser's CURRENT behavior against the frozen `boundary_controls.json`
corpus: heading classification, claim admission, necessity, and (for
the severity-tier controls) actual JobRequirement/UnparsedClaim counts
plus assessable_count/alignment_score via the real matcher+assessment
pipeline with a deterministic, empty candidate fixture.

Evaluation-only. Imports production code read-only; writes no
production code; never mutates gold after its freeze point.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gitscore.assessment import assess_job  # noqa: E402
from gitscore.evidence import build_candidate_evidence_profile  # noqa: E402
from gitscore.jobs.parsing.parser import parse_job_description_with_diagnostics  # noqa: E402
from gitscore.jobs.parsing.segmentation import _classify_heading_line, _line_content_span  # noqa: E402
from gitscore.matching import match_job  # noqa: E402

GOLD_PATH = REPO_ROOT / "evaluation" / "m11g7" / "boundary_controls.json"
FREEZE_PATH = REPO_ROOT / "evaluation" / "m11g7" / "gold_hash_freeze.json"
OUT_PATH = REPO_ROOT / "evaluation" / "reports" / "m11g7_phase1_current_behavior.json"

CANDIDATE = build_candidate_evidence_profile("test-candidate", discovered=(), analyzed=(), evidence_items=())


def current_heading_classification(heading_line: str | None) -> str:
    if heading_line is None:
        return "NOT_A_HEADING"
    span = _line_content_span(heading_line, 0)
    if span is None:
        return "NOT_A_HEADING"
    content = heading_line[span[0]:span[1]]
    classified = _classify_heading_line(heading_line, content)
    return classified.name if classified is not None else "NOT_A_HEADING"


def build_description(control: dict) -> str:
    lines = []
    if control["heading_line"] is not None:
        lines.append(control["heading_line"])
    lines.extend(control["body_lines"])
    return "\n".join(lines) + "\n"


def main() -> None:
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "evaluation_lib"))
    from gold_integrity import verify_frozen_file  # M11-G14: line-ending-portable; raises if gold drifted
    verify_frozen_file(GOLD_PATH, FREEZE_PATH)

    rows = []
    heading_mismatches = []
    false_requirement_fabrications = []
    silent_suppressions = []

    for control in gold["controls"]:
        description = build_description(control)
        current_kind = current_heading_classification(control["heading_line"])
        expected_kind = control["expected_heading_kind"]
        kind_match = current_kind == expected_kind
        if not kind_match:
            heading_mismatches.append(control["id"])

        parsed = parse_job_description_with_diagnostics(description)
        n_requirements = len(parsed.profile.requirements)
        n_unparsed = len(parsed.unparsed_claims)

        match = match_job(CANDIDATE, parsed.profile)
        assessment = assess_job(match)

        # Safety checks, independent of heading-kind matching: did any
        # non-qualification line become a SCORED JobRequirement
        # (fabrication), or did any genuine qualification with a local
        # marker get totally lost (zero admission at all)?
        narrative_texts = {
            q["text"] for q in control["body_qualifications"] if not q["is_genuine_qualification"]
        }
        for req in parsed.profile.requirements:
            req_text = description[req.source_span.start:req.source_span.end]
            if req_text in narrative_texts:
                false_requirement_fabrications.append({
                    "id": control["id"], "text_snippet_len": len(req_text),
                    "necessity": str(req.necessity), "assessable": match.requirement_matches[
                        parsed.profile.requirements.index(req)].status.name,
                })

        admitted_texts = (
            [description[r.source_span.start:r.source_span.end] for r in parsed.profile.requirements]
            + [description[u.source_span.start:u.source_span.end] for u in parsed.unparsed_claims]
        )
        for q in control["body_qualifications"]:
            if q["is_genuine_qualification"] and q["should_enter_assessment"]:
                found = any(q["text"] in t or t in q["text"] for t in admitted_texts)
                if not found:
                    silent_suppressions.append({"id": control["id"], "text_len": len(q["text"])})

        rows.append({
            "id": control["id"],
            "category": control["category"],
            "severity_tier": control.get("severity_tier"),
            "expected_heading_kind": expected_kind,
            "current_heading_kind": current_kind,
            "heading_kind_matches_gold": kind_match,
            "current_n_job_requirements": n_requirements,
            "current_n_unparsed_claims": n_unparsed,
            "current_assessable_count": assessment.assessable_count,
            "current_alignment_score": assessment.alignment_score,
        })

    out = {
        "corpus_version": gold["corpus_version"],
        "gold_hash_verified": True,  # verify_frozen_file() above raises otherwise
        "n_controls": len(gold["controls"]),
        "n_heading_kind_mismatches": len(heading_mismatches),
        "heading_kind_mismatch_ids": heading_mismatches,
        "n_false_requirement_fabrications": len(false_requirement_fabrications),
        "false_requirement_fabrications": false_requirement_fabrications,
        "n_silent_suppressions": len(silent_suppressions),
        "silent_suppressions": silent_suppressions,
        "rows": rows,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {len(rows)} rows to {OUT_PATH}")
    print(f"heading-kind mismatches: {len(heading_mismatches)}")
    print(f"FALSE REQUIREMENT FABRICATIONS (non-qualification scored as JobRequirement): {len(false_requirement_fabrications)}")
    print(f"SILENT SUPPRESSIONS (genuine qualification totally lost): {len(silent_suppressions)}")


if __name__ == "__main__":
    main()
