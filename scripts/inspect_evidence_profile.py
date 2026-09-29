"""Milestone 5D -- manual inspection tool for the V2 evidence pipeline.

Runs `gitscore.pipeline.evidence.extract_candidate_evidence()` against a
REAL GitHub account and prints a detailed report: repositories
discovered/analyzed/partially-analyzed, evidence by type, concepts
detected, representative provenance, unresolved concepts, unknown
dependencies, extractor failures, and the actual number of GitHub API
requests made.

This is inspection-only -- it does not persist anything, does not touch
the database, does not compute a job-fit/readiness score of any kind, and
does not call `pipeline.analyze.analyze_user()` (V1).

Usage:
    python scripts/inspect_evidence_profile.py <username> [--top N]
"""
from __future__ import annotations

import argparse
import io
import sys
import time

# README text can contain arbitrary Unicode (emoji, non-Latin scripts);
# the Windows console's default codepage can't encode all of it. Replace
# rather than crash -- this is a display concern for this inspection
# script only, not a pipeline correctness issue.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from gitscore.github.client import GitHubClient
from gitscore.ranking.config import DEFAULT_TOP_N


class CountingGitHubClient(GitHubClient):
    """Same as GitHubClient, but counts every actual HTTP request made --
    including internal pagination pages -- for an accurate real-world API
    cost measurement (Milestone 5D Part 17/19), not just a call-site count.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request_count = 0

    def _get(self, url, params=None):
        self.request_count += 1
        return super()._get(url, params=params)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP_N)
    args = parser.parse_args(argv)

    # Imported here (not at module scope) so this script fails loudly and
    # specifically if the pipeline import graph is broken, rather than a
    # generic import error before argparse even runs.
    from gitscore.pipeline.evidence import extract_candidate_evidence

    client = CountingGitHubClient()
    start = time.monotonic()
    result = extract_candidate_evidence(args.username, client=client, top_n=args.top)
    elapsed = time.monotonic() - start

    profile = result.profile
    coverage = profile.coverage

    print(f"=== {args.username} -- Milestone 5D evidence extraction ===")
    print(f"elapsed: {elapsed:.1f}s   API requests: {client.request_count}")
    print(
        f"repositories discovered: {coverage.discovered_count}   "
        f"analyzed: {coverage.analyzed_count}   "
        f"partially analyzed: {coverage.partially_analyzed_count}"
    )
    print(f"evidence items: {len(profile.evidence)}   concepts detected: {len(profile.concept_summaries)}")
    print(f"evidence_schema_version={profile.evidence_schema_version} "
          f"concept_registry_version={profile.concept_registry_version}")

    print("\n-- selected (analyzed) repositories --")
    for identity in coverage.analyzed:
        flag = " [partial]" if identity in coverage.partially_analyzed else ""
        print(f"  {identity.owner}/{identity.name}{flag}")

    not_analyzed = set(coverage.discovered) - set(coverage.analyzed)
    if not_analyzed:
        print(f"\n-- discovered but NOT analyzed ({len(not_analyzed)}) --")
        for identity in sorted(not_analyzed, key=lambda r: r.name):
            print(f"  {identity.owner}/{identity.name}")

    print("\n-- evidence by type --")
    by_type: dict[str, int] = {}
    for item in profile.evidence:
        by_type[item.evidence_type.value] = by_type.get(item.evidence_type.value, 0) + 1
    for evidence_type, count in sorted(by_type.items()):
        print(f"  {evidence_type}: {count}")

    print("\n-- concepts detected (resolved) --")
    unresolved = []
    for concept_id, summary in sorted(profile.concept_summaries.items()):
        if concept_id.startswith("unresolved:"):
            unresolved.append((concept_id, summary))
            continue
        repos = ", ".join(f"{r.owner}/{r.name}" for r in summary.repositories)
        print(f"  {concept_id}  (evidence={summary.evidence_count}, strongest={summary.strongest_confidence.name}) <- {repos}")

    if unresolved:
        print("\n-- unresolved concepts --")
        for concept_id, summary in unresolved:
            print(f"  {concept_id}  (evidence={summary.evidence_count})")

    if result.unknown_dependency_names:
        print(f"\n-- unknown dependency names ({len(result.unknown_dependency_names)}) --")
        for name in result.unknown_dependency_names:
            print(f"  {name}")

    if result.extractor_failures:
        print(f"\n-- extractor failures ({len(result.extractor_failures)}) --")
        for failure in result.extractor_failures:
            print(f"  {failure.repository.owner}/{failure.repository.name}  [{failure.source}]  {failure.error}")

    print("\n-- representative provenance (first 5 evidence items) --")
    for item in sorted(profile.evidence, key=lambda e: (e.repository.name, e.evidence_type.value))[:5]:
        print(
            f"  {item.repository.owner}/{item.repository.name}"
            f"  [{item.evidence_type.value}]  {item.concept_id}  "
            f"confidence={item.confidence.name}  extractor={item.extractor_version}\n"
            f"      file_path={item.file_path!r}  raw_observation={item.raw_observation!r}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
