"""Milestone 9B Phase 2 -- CLI entry point for the retrieval-sensitivity
evaluation.

Runs the real `extract_candidate_evidence()` -> `match_job()` ->
`assess_job()` composition twice per synthetic case (generic-only vs.
job-aware retrieval) against `evaluation/m9b/retrieval/`'s synthetic
fixtures, and reports retrieval success, new evidence discovery, new
requirement support, and alignment-score impact as four SEPARATE
measurements per case (see `evaluation_lib/retrieval_sensitivity_eval.py`'s
module docstring).

This does not modify or re-run `scripts/evaluate_repository_retrieval.py`
or `scripts/evaluate_end_to_end_job_aware.py` -- those continue to
measure the REAL candidate fixtures and are cited, not duplicated, in
this milestone's report.

Usage:
    python scripts/evaluate_m9b_retrieval_sensitivity.py

Exit code: 0 on a successful run, 1 only for a missing/malformed fixture
file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from evaluation_lib import report as report_mod
from evaluation_lib import retrieval_sensitivity_eval as rs_eval

RETRIEVAL_DIR = REPO_ROOT / "evaluation" / "m9b" / "retrieval"
REPORT_DIR = REPO_ROOT / "evaluation" / "reports"


def _load(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"HARNESS ERROR: missing {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"HARNESS ERROR: malformed JSON in {path}: {exc}")


def main() -> int:
    try:
        candidates_doc = _load(RETRIEVAL_DIR / "synthetic_candidates.json")
        jobs_doc = _load(RETRIEVAL_DIR / "synthetic_jobs.json")
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 1

    fixtures_by_candidate = {f["candidate"]: f for f in candidates_doc["fixtures"]}
    jobs = jobs_doc["jobs"]

    cases = rs_eval.evaluate_cases(jobs, fixtures_by_candidate)
    metrics = rs_eval.aggregate_metrics(cases)

    star_check = rs_eval.star_dominance_check(
        jobs["m9b_rust_or_go_backend_01"],
        fixtures_by_candidate["crowded_polyglot_dev"],
        popular_repo="viral-js-framework",
        ordinary_repo="js-service-01",
    )

    json_report = {
        "corpus_version": jobs_doc["corpus_version"],
        "metrics": metrics,
        "star_dominance_check": star_check,
        "cases": [
            {
                "job_id": c.job_id,
                "candidate": c.candidate,
                "test_intent": c.test_intent,
                "generic_selected_count": len(c.generic_selected),
                "job_aware_selected_count": len(c.job_aware_selected),
                "job_relevant_additions": list(c.job_relevant_additions),
                "retrieval_success_A": c.retrieval_success,
                "new_evidence_concepts_B": list(c.new_evidence_concepts),
                "newly_supported_requirements_C": list(c.newly_supported_requirements),
                "still_not_observed": list(c.still_not_observed),
                "not_assessable_count": c.not_assessable_count,
                "alignment_before": c.alignment_before,
                "alignment_after": c.alignment_after,
                "required_before": c.required_before,
                "required_after": c.required_after,
                "preferred_before": c.preferred_before,
                "preferred_after": c.preferred_after,
                "score_changed_D": c.score_changed,
                "score_change_justified": c.score_change_justified,
                "justification_note": c.justification_note,
            }
            for c in cases
        ],
    }
    report_mod.write_json_report(REPORT_DIR / "m9b_retrieval_sensitivity_report.json", json_report)

    lines = [
        "# Milestone 9B Phase 2 -- Retrieval-Sensitive End-to-End Evaluation (Synthetic Fixtures)",
        "",
        f"Corpus version: `{jobs_doc['corpus_version']}`",
        "",
        "Four events measured independently per case: (A) retrieval success, (B) new evidence discovery, "
        "(C) new requirement support, (D) alignment-score impact. See module docstring for why these must "
        "never be conflated.",
        "",
    ]
    lines += report_mod.markdown_table(
        ["job_id", "A: retrieved?", "B: new concepts", "C: newly SUPPORTED", "D: score before->after", "justified?"],
        [
            [
                c.job_id, c.retrieval_success, ", ".join(c.new_evidence_concepts) or "(none)",
                ", ".join(c.newly_supported_requirements) or "(none)",
                f"{c.alignment_before} -> {c.alignment_after}",
                c.score_change_justified,
            ]
            for c in cases
        ],
    )
    lines += [
        "",
        "## Common-language repository dominance check",
        "",
        f"`{star_check['popular_repo']}` ({star_check['popular_repo_stars']} stars) relevance score: "
        f"{star_check['popular_repo_relevance_score']}  |  `{star_check['ordinary_repo']}` "
        f"({star_check['ordinary_repo_stars']} stars) relevance score: {star_check['ordinary_repo_relevance_score']}  |  "
        f"equal despite the star gap: {star_check['scores_equal_despite_star_gap']}",
        "",
    ]
    lines += ["## Per-case detail", ""]
    for c in cases:
        lines += [
            f"### {c.job_id} (candidate: {c.candidate})",
            f"- Test intent: {c.test_intent}",
            f"- Generic selection: {len(c.generic_selected)} repos",
            f"- Job-aware selection: {len(c.job_aware_selected)} repos; additions: {list(c.job_relevant_additions)}",
            f"- (A) Retrieval success: {c.retrieval_success}",
            f"- (B) New evidence concepts gained: {list(c.new_evidence_concepts)}",
            f"- (C) Requirements newly SUPPORTED: {list(c.newly_supported_requirements)}",
            f"- Requirements still NOT_OBSERVED after retrieval: {list(c.still_not_observed)}",
            f"- NOT_ASSESSABLE requirement count: {c.not_assessable_count}",
            f"- (D) alignment_score: {c.alignment_before} -> {c.alignment_after}",
            f"       required: {c.required_before} -> {c.required_after}",
            f"       preferred: {c.preferred_before} -> {c.preferred_after}",
            f"- Score change justified: {c.score_change_justified} ({c.justification_note})",
            "",
        ]
    report_mod.write_text_report(REPORT_DIR / "m9b_retrieval_sensitivity_report.md", lines)

    print(json.dumps(metrics, indent=2))
    for c in cases:
        print(f"{c.job_id}: A={c.retrieval_success} B={bool(c.new_evidence_concepts)} "
              f"C={bool(c.newly_supported_requirements)} D={c.score_changed} "
              f"({c.alignment_before}->{c.alignment_after}) justified={c.score_change_justified}")
    print(f"Report written to {REPORT_DIR / 'm9b_retrieval_sensitivity_report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
