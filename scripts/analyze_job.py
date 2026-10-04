"""Milestone 7C -- developer smoke path for the end-to-end job-analysis
orchestration (`gitscore.application.job_fit.analyze_job_fit`).

Runs the REAL pipeline against a REAL GitHub account: candidate evidence
collection -> job-description parsing -> matching -> GitHub Evidence
Alignment assessment. Inspection-only -- does not persist anything, does
not touch the database, and prints a concise structured summary, not a
polished report (that is a future API/UI layer's job).

Usage:
    python scripts/analyze_job.py <username> <job_description_file> [--top N]
"""
from __future__ import annotations

import argparse
import io
import sys

# Job-description text and READMEs can contain arbitrary Unicode; the
# Windows console's default codepage can't encode all of it. Replace
# rather than crash -- a display concern for this script only.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from gitscore.ranking.config import DEFAULT_TOP_N


def _print_requirement_group(label, matches):
    print(f"\n{label}:")
    if not matches:
        print("  (none)")
        return
    for match in matches:
        print(f"  - {match.requirement.original_text.strip()}")


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    parser.add_argument("job_description_file")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP_N)
    args = parser.parse_args(argv)

    # Imported here (not at module scope) so this script fails loudly and
    # specifically if the pipeline import graph is broken, rather than a
    # generic import error before argparse even runs.
    from gitscore.application import analyze_job_fit

    with open(args.job_description_file, "r", encoding="utf-8") as f:
        job_description = f.read()

    result = analyze_job_fit(args.username, job_description, top_n=args.top)
    assessment = result.assessment
    coverage = result.candidate_profile.coverage

    print(f"=== {args.username} -- GitHub Evidence Alignment ===")
    score = assessment.alignment_score
    print(f"GitHub Evidence Alignment: {score if score is not None else 'N/A (nothing assessable)'}")

    required = assessment.required
    preferred = assessment.preferred
    print(f"Required: {f'{required.supported} of {required.assessable}' if required else 'N/A'} supported")
    print(f"Preferred: {f'{preferred.supported} of {preferred.assessable}' if preferred else 'N/A'} supported")

    print(f"\nRepositories analyzed: {coverage.analyzed_count} of {coverage.discovered_count}")
    if coverage.partially_analyzed_count:
        print(f"Repositories with a partial extraction failure: {coverage.partially_analyzed_count}")

    _print_requirement_group("Supported", assessment.supported_matches())
    _print_requirement_group("Not observed", assessment.not_observed_matches())
    _print_requirement_group("Not assessable", assessment.not_assessable_matches())

    if result.extractor_failures:
        print(f"\n-- extractor failures ({len(result.extractor_failures)}) --")
        for failure in result.extractor_failures:
            print(f"  {failure.repository.owner}/{failure.repository.name}  [{failure.source}]  {failure.error}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
