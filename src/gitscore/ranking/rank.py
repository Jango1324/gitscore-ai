"""Milestone 5B -- deterministic, job-independent repository ranking.

Answers one question: "which of this candidate's repositories best
represent substantive technical work, and are therefore worth a deep
(per-repository) fetch later?" It does not decide job fit, ML
relevance, or documentation quality -- see
docs/design/MILESTONE_5A_JOB_MATCHING_DESIGN.md Part 11.

Operates entirely on repository-listing summaries (see
gitscore.github.parser.parse_repo_summary) already available from
GitHubClient.get_repositories() -- no additional API requests. An
optional list of caller-supplied relevance terms provides a Stage-2
boost (Milestone 5A Part 3 / this milestone's Part 3); without it,
ranking is pure Stage-1 substantiveness. This is NOT the future Job
Requirement Parser -- there is no NLP here, only a capped, literal
keyword-overlap boost over already-fetched text.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from gitscore.ranking.config import DEFAULT_TOP_N, RankingWeights

_TERM_PATTERN_CACHE: dict[str, "re.Pattern[str]"] = {}


def _term_pattern(term: str):
    pattern = _TERM_PATTERN_CACHE.get(term)
    if pattern is None:
        # Same word-boundary approach as features/ml.py's ML_KEYWORDS
        # matching: a standalone token, not a substring inside another
        # word (e.g. "ai" must not match inside "container").
        pattern = re.compile(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])")
        _TERM_PATTERN_CACHE[term] = pattern
    return pattern


def _parse_github_timestamp(value):
    if not value:
        return None
    try:
        # GitHub timestamps are ISO 8601 UTC with a trailing "Z".
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


@dataclass(frozen=True)
class RepositoryRankingResult:
    """One repository's ranking outcome, with its full score breakdown.

    `components` and `multipliers` are kept on the result (not just the
    final `score`) specifically so a human can answer "why did this repo
    rank highly" without re-deriving the math -- see Milestone 5B Part 5.
    """

    name: str
    score: float
    components: dict
    multipliers: dict
    is_fork: bool
    archived: bool
    size_kb: int
    stars: int
    primary_language: object
    pushed_at: object
    relevance_hits: tuple = field(default_factory=tuple)


def _size_score(size_kb, weights: RankingWeights) -> float:
    size_kb = max(0.0, float(size_kb or 0))
    if size_kb <= 0:
        return 0.0
    return min(1.0, math.log10(1 + size_kb) / math.log10(1 + weights.size_reference_kb))


def _recency_score(pushed_at, weights: RankingWeights, reference_time: datetime) -> float:
    pushed = _parse_github_timestamp(pushed_at)
    if pushed is None:
        return 0.0
    days_since = max(0.0, (reference_time - pushed).total_seconds() / 86400.0)
    return math.exp(-days_since / weights.recency_half_life_days)


def _star_score(stars, weights: RankingWeights) -> float:
    stars = max(0, int(stars or 0))
    if stars <= 0:
        return 0.0
    return min(1.0, math.log10(1 + stars) / math.log10(1 + weights.star_reference))


def _relevance_hits(summary: dict, relevance_terms) -> tuple:
    if not relevance_terms:
        return ()
    text_parts = [
        summary.get("name") or "",
        summary.get("description") or "",
        summary.get("primary_language") or "",
    ]
    text_parts.extend(summary.get("topics") or [])
    text = " ".join(text_parts).lower()
    return tuple(term for term in relevance_terms if _term_pattern(term).search(text))


def score_repository(
    summary: dict,
    weights: RankingWeights | None = None,
    relevance_terms=None,
    reference_time: datetime | None = None,
) -> RepositoryRankingResult:
    """Score one repository summary (shaped like `parse_repo_summary`'s output).

    `relevance_terms` is the OPTIONAL Stage-2 boost: a plain list of
    normalized strings supplied directly by the caller for testing (e.g.
    ``["postgresql", "python", "docker"]``). This is NOT job-description
    parsing -- there is no extraction step, only a literal, capped
    keyword-overlap boost against the repo's own name/description/
    language/topics. Ranking is identical to Stage-1-only when
    `relevance_terms` is None or empty.
    """
    weights = weights or RankingWeights()
    reference_time = reference_time or datetime.now(timezone.utc)

    components = {
        "size": _size_score(summary.get("size_kb"), weights),
        "recency": _recency_score(summary.get("pushed_at"), weights, reference_time),
        "language": 1.0 if summary.get("primary_language") else 0.0,
        "description": 1.0 if (summary.get("description") or "").strip() else 0.0,
        "stars": _star_score(summary.get("stars"), weights),
    }

    base_score = (
        weights.w_size * components["size"]
        + weights.w_recency * components["recency"]
        + weights.w_language * components["language"]
        + weights.w_description * components["description"]
        + weights.w_stars * components["stars"]
    )

    size_kb = float(summary.get("size_kb") or 0)
    multipliers = {
        "fork": weights.fork_multiplier if summary.get("is_fork") else 1.0,
        "archived": weights.archived_multiplier if summary.get("archived") else 1.0,
        "trivial": weights.trivial_multiplier if size_kb <= weights.trivial_size_kb_threshold else 1.0,
    }

    relevance_hits = _relevance_hits(summary, relevance_terms)
    if relevance_terms:
        relevance_fraction = len(relevance_hits) / len(relevance_terms)
        multipliers["relevance_boost"] = 1.0 + weights.relevance_boost_weight * relevance_fraction
    else:
        multipliers["relevance_boost"] = 1.0

    final_score = base_score
    for multiplier in multipliers.values():
        final_score *= multiplier

    return RepositoryRankingResult(
        name=summary["name"],
        score=final_score,
        components=components,
        multipliers=multipliers,
        is_fork=bool(summary.get("is_fork")),
        archived=bool(summary.get("archived")),
        size_kb=int(size_kb),
        stars=int(summary.get("stars") or 0),
        primary_language=summary.get("primary_language"),
        pushed_at=summary.get("pushed_at"),
        relevance_hits=relevance_hits,
    )


def _sort_key(result: RepositoryRankingResult):
    # Deterministic tie-break (Milestone 5B Part 7):
    #   1. score, descending
    #   2. pushed_at, descending (missing/unparseable sorts as oldest)
    #   3. repository name, ascending, case-insensitive
    pushed = _parse_github_timestamp(result.pushed_at)
    pushed_key = pushed.timestamp() if pushed is not None else float("-inf")
    return (-result.score, -pushed_key, result.name.lower())


def rank_repositories(
    summaries,
    top_n: int = DEFAULT_TOP_N,
    weights: RankingWeights | None = None,
    relevance_terms=None,
    reference_time: datetime | None = None,
) -> list:
    """Rank repository summaries and return the top `top_n`.

    `summaries` is a list of dicts shaped like
    `gitscore.github.parser.parse_repo_summary`'s output. If fewer than
    `top_n` repositories are given, ALL of them are returned, ranked --
    never padded (Milestone 5B Part 4). If more are given, exactly
    `top_n` are returned.

    Determinism (Milestone 5B Part 7): for a fixed `reference_time`, the
    same input summaries + the same `weights` always produce the same
    output order. `reference_time` defaults to "now" and is resolved
    once per call, then reused for every repository scored in that call,
    so a single ranking invocation cannot drift mid-computation. Two
    separate calls made at different real-world times may legitimately
    reorder repositories as recency scores decay -- that is intended
    behavior, not nondeterminism; callers who need byte-for-byte
    reproducible results across time should pass an explicit
    `reference_time`.
    """
    weights = weights or RankingWeights()
    reference_time = reference_time or datetime.now(timezone.utc)

    scored = [
        score_repository(
            summary,
            weights=weights,
            relevance_terms=relevance_terms,
            reference_time=reference_time,
        )
        for summary in summaries
    ]
    scored.sort(key=_sort_key)
    return scored[:top_n]
