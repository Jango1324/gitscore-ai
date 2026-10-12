"""Milestone 8E -- additive harness: does job-aware retrieval (8D.2)
change the end-to-end candidate x job matrix at all?

`scripts/evaluate_end_to_end.py` (8C/8D.1/8D.3, unmodified) calls
`extract_candidate_evidence()` ONCE per candidate with no
`job_relevance_terms`, and reuses that single job-independent profile
across every job pair in `evaluation/gold/matrix.json`. It therefore
never exercises `gitscore.application.job_fit.analyze_job_fit()`'s own
composition, which threads `job_relevance_terms` through
`_relevance_terms_from_job_profile()` on every call. This script
mirrors `analyze_job_fit()`'s REAL composition exactly (importing its
private bridge function rather than reimplementing it) and diffs the
result against the already-committed, job-independent
`evaluation/reports/end_to_end_report.json` cells for the same
candidate/job_id pairs.

Does not modify `evaluate_end_to_end.py` or any existing
`evaluation_lib` module. Writes its own report,
`evaluation/reports/end_to_end_job_aware_report.json` -- never
overwrites the existing `end_to_end_report.*` files.

Usage:
    python scripts/evaluate_end_to_end_job_aware.py

Exit code: 0 on a successful run, 1 only for a harness/fixture-level
error (mirrors the other scripts/evaluate_*.py files).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from gitscore.application.job_fit import _relevance_terms_from_job_profile
from gitscore.assessment import assess_job
from gitscore.jobs import parse_job_description
from gitscore.matching import match_job
from gitscore.pipeline.evidence import extract_candidate_evidence

from evaluation_lib import report as report_mod
from evaluation_lib.loaders import (
    EvaluationFixtureError,
    build_fake_client,
    list_candidate_names,
    list_job_ids,
    load_candidate_fixture,
    load_job,
)

REPORT_DIR = REPO_ROOT / "evaluation" / "reports"
MATRIX_PATH = REPO_ROOT / "evaluation" / "gold" / "matrix.json"
EXISTING_E2E_REPORT_PATH = REPORT_DIR / "end_to_end_report.json"


def main() -> int:
    try:
        if not MATRIX_PATH.exists():
            raise EvaluationFixtureError(f"missing {MATRIX_PATH}")
        matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))

        if not EXISTING_E2E_REPORT_PATH.exists():
            raise EvaluationFixtureError(f"missing {EXISTING_E2E_REPORT_PATH} -- run scripts/evaluate_end_to_end.py first")
        existing_report = json.loads(EXISTING_E2E_REPORT_PATH.read_text(encoding="utf-8"))
        existing_cells = {(c["candidate"], c["job_id"]): c for c in existing_report["cells"]}

        candidate_names = list_candidate_names()
        fixtures = {}
        for pair in matrix["pairs"]:
            name = pair["candidate"]
            match = next((n for n in candidate_names if n.lower() == name.lower()), None)
            if match is None:
                raise EvaluationFixtureError(f"matrix references unknown candidate fixture: {name}")
            fixtures[name] = load_candidate_fixture(match)

        job_ids = list_job_ids()
        jobs = {job_id: load_job(job_id) for job_id in job_ids}
        for pair in matrix["pairs"]:
            if pair["job_id"] not in jobs:
                raise EvaluationFixtureError(f"matrix references unknown job_id: {pair['job_id']}")
    except EvaluationFixtureError as exc:
        print(f"HARNESS ERROR: {exc}", file=sys.stderr)
        return 1

    rows = []
    for pair in matrix["pairs"]:
        candidate_name = pair["candidate"]
        job_id = pair["job_id"]
        fixture = fixtures[candidate_name]
        job = jobs[job_id]

        # -- job-independent baseline, freshly recomputed (should match
        # the committed end_to_end_report.json cell exactly; recomputing
        # rather than trusting the file catches any drift). --
        baseline_client = build_fake_client(fixture)
        baseline_result = extract_candidate_evidence(candidate_name, client=baseline_client, top_n=fixture["top_n"])
        baseline_names = {r.name for r in baseline_result.profile.coverage.analyzed}

        # -- real analyze_job_fit() composition: job parsed first, its
        # requirements bridged to JobRelevanceTerms, THEN evidence
        # extraction runs WITH those terms. --
        job_profile = parse_job_description(job["raw_text"], title=job.get("title"))
        relevance_terms = _relevance_terms_from_job_profile(job_profile)

        job_aware_client = build_fake_client(fixture)
        job_aware_result = extract_candidate_evidence(
            candidate_name, client=job_aware_client, top_n=fixture["top_n"], job_relevance_terms=relevance_terms
        )
        job_aware_names = {r.name for r in job_aware_result.profile.coverage.analyzed}

        # Both assessments run through match_job()/assess_job() with the
        # SAME current code and SAME job_profile -- the only variable is
        # whether evidence extraction saw job_relevance_terms. This
        # isolates the 8D.2 retrieval effect from any unrelated code
        # change (e.g. 8D.3's README-attribution fix) that may make the
        # job-INDEPENDENT baseline differ from the committed, possibly
        # stale `end_to_end_report.json` cell -- that file is reported
        # separately below for context, never used as the comparison
        # baseline itself.
        baseline_match_analysis = match_job(baseline_result.profile, job_profile)
        baseline_assessment = assess_job(baseline_match_analysis)

        match_analysis = match_job(job_aware_result.profile, job_profile)
        assessment = assess_job(match_analysis)

        existing_cell = existing_cells.get((candidate_name, job_id))
        committed_alignment = existing_cell["alignment_score"] if existing_cell else None

        old_alignment = baseline_assessment.alignment_score
        old_required = (
            (baseline_assessment.required.supported, baseline_assessment.required.assessable)
            if baseline_assessment.required else None
        )
        old_preferred = (
            (baseline_assessment.preferred.supported, baseline_assessment.preferred.assessable)
            if baseline_assessment.preferred else None
        )

        new_alignment = assessment.alignment_score
        new_required = (assessment.required.supported, assessment.required.assessable) if assessment.required else None
        new_preferred = (assessment.preferred.supported, assessment.preferred.assessable) if assessment.preferred else None

        newly_analyzed = sorted(job_aware_names - baseline_names)
        changed = (old_alignment != new_alignment) or (old_required != new_required) or (old_preferred != new_preferred)

        rows.append({
            "candidate": candidate_name,
            "job_id": job_id,
            "committed_report_alignment": committed_alignment,
            "old_alignment": old_alignment,
            "new_alignment": new_alignment,
            "old_required": old_required,
            "new_required": new_required,
            "old_preferred": old_preferred,
            "new_preferred": new_preferred,
            "changed": changed,
            "newly_analyzed_repos": newly_analyzed,
            "baseline_analyzed_count": len(baseline_names),
            "job_aware_analyzed_count": len(job_aware_names),
        })

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORT_DIR / "end_to_end_job_aware_report.json"
    report_mod.write_json_report(out_path, {"pairs": rows})

    changed_rows = [r for r in rows if r["changed"]]
    stale_rows = [r for r in rows if r["committed_report_alignment"] != r["old_alignment"]]

    print(f"{'candidate':<14}{'job_id':<24}{'base':>5}{'jobaw':>6}  {'base_req':<10}{'jobaw_req':<10}{'chg':<6}newly_analyzed")
    for r in rows:
        print(
            f"{r['candidate']:<14}{r['job_id']:<24}{str(r['old_alignment']):>5}{str(r['new_alignment']):>6}  "
            f"{str(r['old_required']):<10}{str(r['new_required']):<10}{str(r['changed']):<6}"
            f"{', '.join(r['newly_analyzed_repos']) or '(none)'}"
        )

    print()
    print(f"Pairs evaluated: {len(rows)}")
    print(f"Pairs changed by job-aware retrieval (same current code, relevance terms on/off): {len(changed_rows)}")
    for r in changed_rows:
        print(
            f"  CHANGED: {r['candidate']} x {r['job_id']}: alignment {r['old_alignment']} -> {r['new_alignment']}, "
            f"required {r['old_required']} -> {r['new_required']}, newly_analyzed={r['newly_analyzed_repos']}"
        )
    if stale_rows:
        print()
        print(f"NOTE: {len(stale_rows)} pair(s) where the committed end_to_end_report.json cell disagrees with a "
              f"freshly recomputed job-independent baseline under CURRENT code (unrelated to job-aware retrieval -- "
              f"e.g. a later milestone's fix the committed report predates):")
        for r in stale_rows:
            print(f"  {r['candidate']} x {r['job_id']}: committed={r['committed_report_alignment']} fresh_baseline={r['old_alignment']}")
    print(f"Report written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
