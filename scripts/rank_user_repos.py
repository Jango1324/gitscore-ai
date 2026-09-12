"""Milestone 5B -- manual inspection tool for repository ranking.

Fetches a user's repository listing (one GitHub call for the user, plus
pagination of the repo-list endpoint -- the SAME calls
`gitscore.pipeline.analyze.analyze_user()` already makes before it starts
per-repository languages/README fetches) and prints the top-N ranked
repositories with their full score breakdown, so a human can sanity-check
whether the ranking looks reasonable.

This performs NO per-repository API calls (no languages, no README) --
it only exercises Stage 1 (+ optional Stage 2 relevance boost) repository
ranking. It does not persist anything, does not call analyze_user(), and
does not touch the database.

Usage:
    python scripts/rank_user_repos.py <username> [--top N] [--relevance term1,term2,...]
"""
import argparse
import sys

from gitscore.github.client import GitHubClient
from gitscore.github.parser import parse_repo_summary
from gitscore.ranking import DEFAULT_TOP_N, rank_repositories


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP_N)
    parser.add_argument("--relevance", default=None, help="comma-separated terms, e.g. postgresql,python,docker")
    args = parser.parse_args(argv)

    relevance_terms = [t.strip() for t in args.relevance.split(",")] if args.relevance else None

    client = GitHubClient()
    raw_repos = client.get_repositories(args.username)
    summaries = [parse_repo_summary(r) for r in raw_repos]

    ranked = rank_repositories(summaries, top_n=args.top, relevance_terms=relevance_terms)

    print(f"{args.username}: {len(raw_repos)} total repositories, showing top {len(ranked)}\n")
    for i, r in enumerate(ranked, 1):
        flags = []
        if r.is_fork:
            flags.append("fork")
        if r.archived:
            flags.append("archived")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        print(f"{i:>2}. {r.name}{flag_str}  score={r.score:.3f}")
        print(
            f"      components: size={r.components['size']:.2f} recency={r.components['recency']:.2f} "
            f"language={r.components['language']:.2f} description={r.components['description']:.2f} "
            f"stars={r.components['stars']:.2f}"
        )
        print(
            f"      multipliers: fork={r.multipliers['fork']:.2f} archived={r.multipliers['archived']:.2f} "
            f"trivial={r.multipliers['trivial']:.2f} relevance_boost={r.multipliers['relevance_boost']:.2f}"
        )
        print(
            f"      raw: size_kb={r.size_kb} stars={r.stars} lang={r.primary_language} pushed_at={r.pushed_at}"
            + (f" relevance_hits={r.relevance_hits}" if r.relevance_hits else "")
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
