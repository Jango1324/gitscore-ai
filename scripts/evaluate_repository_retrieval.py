"""Milestone 8D.2 -- repository-retrieval harness: job-aware retrieval
evaluation.

Runs the REAL `extract_candidate_evidence()` + `parse_job_description()`
pipeline against this evaluation's own offline candidate fixtures
(`evaluation/fixtures/candidates/`) and job corpus (`evaluation/jobs/`),
compared against hand-authored gold
(`evaluation/gold/retrieval_cases.json` -- NEW gold introduced by this
milestone, not a correction of any 8c:v1/8c:v1.1 file). No live GitHub
call is made by this script.

For each gold case, classifies the outcome via
`evaluation_lib.retrieval_eval.classify_retrieval_outcome()` into one of
five outcomes that keep relevance ground truth (`genuinely_relevant`)
structurally separate from the observed/expected result
(`expected_analyzed`) -- a genuinely relevant repository that the fixed
retrieval budget still excludes is reported as
`RETRIEVAL_MISSED_RELEVANT`, never folded into the negative-control
bucket. See `retrieval_eval.py`'s module docstring and
`docs/evaluation/MILESTONE_8D2_JOB_AWARE_RETRIEVAL.md` Section 6 for the
full rationale.

Usage:
    python scripts/evaluate_repository_retrieval.py

Exit code: 0 on a successful run (regardless of how many cases'
`prediction_correct` regression pin holds -- those are measurements, not
test assertions, mirroring the other two evaluate_*.py scripts), 1 only
for a harness/fixture-level error.

Does NOT modify or re-run `scripts/evaluate_end_to_end.py` -- that
script continues to call `extract_candidate_evidence()` with no
`job_relevance_terms` (the job-independent default), so its own
published report is untouched by this milestone.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from evaluation_lib import report, retrieval_eval
from evaluation_lib.loaders import (
    EvaluationFixtureError,
    list_candidate_names,
    list_job_ids,
    load_candidate_fixture,
    load_job,
    load_retrieval_cases,
)

REPORT_DIR = REPO_ROOT / "evaluation" / "reports"


def main() -> int:
    try:
        gold = load_retrieval_cases()
        cases = gold["cases"]
        candidate_names = {c["candidate"] for c in cases}
        job_ids = {c["job_id"] for c in cases}

        known_candidates = set(list_candidate_names())
        unknown_candidates = candidate_names - known_candidates
        if unknown_candidates:
            raise EvaluationFixtureError(f"retrieval_cases.json references unknown candidate(s): {sorted(unknown_candidates)}")
        known_jobs = set(list_job_ids())
        unknown_jobs = job_ids - known_jobs
        if unknown_jobs:
            raise EvaluationFixtureError(f"retrieval_cases.json references unknown job_id(s): {sorted(unknown_jobs)}")

        fixtures = {name: load_candidate_fixture(name) for name in candidate_names}
        jobs = {job_id: load_job(job_id) for job_id in job_ids}
    except (EvaluationFixtureError, KeyError) as exc:
        print(f"HARNESS ERROR: {exc}", file=sys.stderr)
        return 1

    case_results = retrieval_eval.evaluate_cases(cases, fixtures, jobs)
    pair_results = retrieval_eval.evaluate_pairs(cases, fixtures, jobs)
    metrics = retrieval_eval.aggregate_metrics(case_results)

    json_report = {
        "corpus_version": gold["corpus_version"],
        "aggregate": metrics,
        "cases": [r.__dict__ for r in case_results],
        "pairs": [r.__dict__ for r in pair_results],
    }
    report.write_json_report(REPORT_DIR / "retrieval_report.json", json_report)

    lines = [
        "# Repository-Retrieval Evaluation Report (Milestone 8D.2)",
        "",
        f"Corpus version: `{gold['corpus_version']}`",
        "",
        "Relevance ground truth (`genuinely_relevant`) is reported SEPARATELY",
        "from the observed outcome -- a genuinely relevant repository the fixed",
        "budget still excludes is a `RETRIEVAL_MISSED_RELEVANT` miss, never a",
        "negative-control success. See the per-case outcome column below.",
        "",
        f"Cases evaluated: {metrics['cases_evaluated']}",
        "",
        "**Genuinely relevant repositories** "
        f"({metrics['genuinely_relevant_cases']} cases):",
        f"- Recovered by job-aware retrieval: {metrics['relevant_recovered_by_job_awareness']}",
        f"- Already covered by generic ranking: {metrics['relevant_already_covered_by_generic_ranking']}",
        f"- **Missed despite job-aware retrieval (known limitation): {metrics['relevant_missed_despite_job_awareness']}**",
        "",
        "**Negative controls (genuinely irrelevant repositories)** "
        f"({metrics['negative_control_cases']} cases):",
        f"- Correctly excluded: {metrics['negative_controls_correctly_excluded']}",
        f"- False-positive additions: {metrics['negative_controls_with_false_positive_addition']}",
        "",
        "Regression pin (`expected_analyzed` vs. measured outcome -- NOT a "
        "relevance judgment): "
        f"{metrics['prediction_matches_expected']}/{metrics['cases_evaluated']} match.",
        "",
        "## Per-case verdicts",
        "",
    ]
    lines += report.markdown_table(
        ["candidate", "job_id", "repo", "genuinely_relevant", "expected_analyzed", "job_aware_analyzed", "outcome"],
        [
            [r.candidate, r.job_id, r.repo, r.genuinely_relevant, r.expected_analyzed, r.job_aware_analyzed, r.outcome]
            for r in case_results
        ],
    )

    lines += ["", "## Per candidate x job pair: full job-aware addition set", ""]
    lines += report.markdown_table(
        ["candidate", "job_id", "generic_analyzed_count", "job_aware_analyzed_count", "job_aware_additions"],
        [
            [p.candidate, p.job_id, p.generic_analyzed_count, p.job_aware_analyzed_count, ", ".join(p.job_aware_additions) or "(none)"]
            for p in pair_results
        ],
    )

    lines += ["", "## Case rationale", ""]
    for r in case_results:
        lines.append(f"- [{r.outcome}] `{r.candidate}` x `{r.job_id}` / `{r.repo}`: {r.rationale}")

    report.write_text_report(REPORT_DIR / "retrieval_report.md", lines)

    print(f"Corpus version: {gold['corpus_version']}")
    print(f"Cases evaluated: {metrics['cases_evaluated']}")
    print(
        f"Genuinely relevant: {metrics['genuinely_relevant_cases']} "
        f"(recovered={metrics['relevant_recovered_by_job_awareness']}, "
        f"already_covered={metrics['relevant_already_covered_by_generic_ranking']}, "
        f"missed={metrics['relevant_missed_despite_job_awareness']})"
    )
    print(
        f"Negative controls: {metrics['negative_control_cases']} "
        f"(correctly_excluded={metrics['negative_controls_correctly_excluded']}, "
        f"false_positive_additions={metrics['negative_controls_with_false_positive_addition']})"
    )
    print(f"Reports written to {REPORT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
