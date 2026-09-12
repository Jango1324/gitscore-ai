"""Milestone 5B: gitscore.ranking (deterministic repository ranking).

All fixtures are synthetic repository summaries shaped like
gitscore.github.parser.parse_repo_summary's output -- no real network
calls, no GitHub token required. `reference_time` is always pinned
explicitly so recency-dependent assertions are reproducible.
"""
from datetime import datetime, timezone

import pytest

from gitscore.ranking import RankingWeights, rank_repositories, score_repository

NOW = datetime(2026, 9, 11, tzinfo=timezone.utc)


def summary(name="repo", **overrides):
    """A repository summary shaped like parse_repo_summary's output."""
    base = {
        "name": name,
        "description": "A real project with a description",
        "primary_language": "Python",
        "is_fork": False,
        "archived": False,
        "size_kb": 500,
        "stars": 3,
        "forks": 0,
        "topics": [],
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "pushed_at": "2026-06-01T00:00:00Z",
        "html_url": f"https://github.com/user/{name}",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Original vs. fork
# ---------------------------------------------------------------------------

def test_fork_ranks_below_an_otherwise_identical_original():
    original = score_repository(summary("original"), reference_time=NOW)
    forked = score_repository(summary("forked", is_fork=True), reference_time=NOW)

    assert forked.score < original.score
    assert forked.multipliers["fork"] < 1.0


def test_fork_is_not_zeroed_out_entirely():
    # A fork may still hold real evidence -- it should be dampened, not excluded.
    forked = score_repository(summary("forked", is_fork=True), reference_time=NOW)
    assert forked.score > 0.0


# ---------------------------------------------------------------------------
# Archived penalty
# ---------------------------------------------------------------------------

def test_archived_ranks_below_an_otherwise_identical_active_repo():
    active = score_repository(summary("active"), reference_time=NOW)
    archived = score_repository(summary("archived", archived=True), reference_time=NOW)

    assert archived.score < active.score
    assert archived.multipliers["archived"] < 1.0


# ---------------------------------------------------------------------------
# Recency
# ---------------------------------------------------------------------------

def test_more_recently_pushed_repo_ranks_higher():
    recent = score_repository(summary("recent", pushed_at="2026-09-01T00:00:00Z"), reference_time=NOW)
    stale = score_repository(summary("stale", pushed_at="2018-01-01T00:00:00Z"), reference_time=NOW)

    assert recent.score > stale.score


def test_missing_pushed_at_scores_as_weakest_recency_not_a_crash():
    result = score_repository(summary("no-push-date", pushed_at=None), reference_time=NOW)
    assert result.components["recency"] == 0.0


# ---------------------------------------------------------------------------
# Size / substantiveness
# ---------------------------------------------------------------------------

def test_larger_repo_scores_higher_up_to_saturation():
    small = score_repository(summary("small", size_kb=50), reference_time=NOW)
    large = score_repository(summary("large", size_kb=2000), reference_time=NOW)
    huge = score_repository(summary("huge", size_kb=200_000), reference_time=NOW)

    assert small.components["size"] < large.components["size"]
    # Saturates: a 200MB repo is not 100x "more substantive" than a 2MB one.
    assert huge.components["size"] == pytest.approx(large.components["size"], abs=1e-6)


def test_trivial_sized_repo_is_heavily_penalized():
    trivial = score_repository(summary("empty-scaffold", size_kb=1), reference_time=NOW)
    substantial = score_repository(summary("real-project", size_kb=500), reference_time=NOW)

    assert trivial.multipliers["trivial"] < 1.0
    assert trivial.score < substantial.score * 0.5


def test_zero_size_does_not_crash_and_scores_at_the_floor():
    result = score_repository(summary("empty-repo", size_kb=0, primary_language=None, description=None), reference_time=NOW)
    assert result.components["size"] == 0.0
    assert result.score >= 0.0


# ---------------------------------------------------------------------------
# Stars must not dominate
# ---------------------------------------------------------------------------

def test_huge_stars_cannot_beat_a_modest_substantive_active_repo():
    viral_but_trivial = score_repository(
        summary(
            "viral-fork",
            stars=50_000,
            size_kb=2,
            pushed_at="2016-01-01T00:00:00Z",
            is_fork=True,
        ),
        reference_time=NOW,
    )
    modest_but_real = score_repository(
        summary("solid-project", stars=1, size_kb=800, pushed_at="2026-08-01T00:00:00Z"),
        reference_time=NOW,
    )

    assert modest_but_real.score > viral_but_trivial.score


def test_star_score_saturates_and_stays_a_minor_component():
    few_stars = score_repository(summary("few-stars", stars=5), reference_time=NOW)
    many_stars = score_repository(summary("many-stars", stars=1_000_000), reference_time=NOW)

    # Star component itself must saturate at 1.0, never exceed it.
    assert many_stars.components["stars"] == pytest.approx(1.0, abs=1e-6)
    # And the weight on that component must be a minority of the total.
    assert RankingWeights().w_stars < 0.5 * sum(
        [RankingWeights().w_size, RankingWeights().w_recency, RankingWeights().w_language, RankingWeights().w_description]
    )
    assert many_stars.score > few_stars.score  # still a real, if small, signal


# ---------------------------------------------------------------------------
# Determinism and tie-breaking
# ---------------------------------------------------------------------------

def test_same_input_produces_the_same_order_every_time():
    repos = [summary(f"repo-{i}", size_kb=100 * i, stars=i) for i in range(10)]

    first = [r.name for r in rank_repositories(repos, top_n=10, reference_time=NOW)]
    second = [r.name for r in rank_repositories(repos, top_n=10, reference_time=NOW)]

    assert first == second


def test_tie_break_uses_pushed_at_then_name():
    # Identical scoring inputs except pushed_at and name -- score ties exactly.
    a = summary("bravo", pushed_at="2025-01-01T00:00:00Z")
    b = summary("alpha", pushed_at="2026-01-01T00:00:00Z")  # more recent -> wins despite name
    c = summary("charlie", pushed_at="2025-01-01T00:00:00Z")  # same pushed_at as "bravo" -> name breaks tie

    ranked = rank_repositories([a, b, c], top_n=3, reference_time=NOW)

    assert [r.name for r in ranked] == ["alpha", "bravo", "charlie"]


def test_exact_score_and_pushed_at_tie_breaks_alphabetically():
    a = summary("zulu")
    b = summary("alpha")

    ranked = rank_repositories([a, b], top_n=2, reference_time=NOW)

    assert [r.name for r in ranked] == ["alpha", "zulu"]


# ---------------------------------------------------------------------------
# Top-N policy
# ---------------------------------------------------------------------------

def test_fewer_than_n_repos_returns_all_without_padding():
    repos = [summary(f"repo-{i}") for i in range(4)]

    ranked = rank_repositories(repos, top_n=15, reference_time=NOW)

    assert len(ranked) == 4


def test_exactly_n_repos_returns_all_n():
    repos = [summary(f"repo-{i}") for i in range(15)]

    ranked = rank_repositories(repos, top_n=15, reference_time=NOW)

    assert len(ranked) == 15


def test_more_than_n_repos_is_truncated_to_exactly_n():
    repos = [summary(f"repo-{i}", size_kb=i) for i in range(40)]

    ranked = rank_repositories(repos, top_n=15, reference_time=NOW)

    assert len(ranked) == 15
    # Truncation keeps the highest-scoring repos, not an arbitrary prefix.
    assert ranked[0].size_kb == 39


def test_giant_repository_list_is_bounded_to_top_n():
    repos = [summary(f"repo-{i}", size_kb=i % 3000, stars=i % 500) for i in range(1200)]

    ranked = rank_repositories(repos, top_n=15, reference_time=NOW)

    assert len(ranked) == 15


def test_empty_repository_list_returns_empty():
    assert rank_repositories([], top_n=15, reference_time=NOW) == []


# ---------------------------------------------------------------------------
# Missing optional metadata degrades gracefully
# ---------------------------------------------------------------------------

def test_missing_language_description_topics_does_not_crash():
    result = score_repository(
        summary("sparse", primary_language=None, description=None, topics=None, pushed_at=None, size_kb=None, stars=None),
        reference_time=NOW,
    )

    assert result.components["language"] == 0.0
    assert result.components["description"] == 0.0
    assert result.score >= 0.0


# ---------------------------------------------------------------------------
# Optional Stage-2 relevance boost
# ---------------------------------------------------------------------------

def test_relevance_boost_favors_a_matching_repo_over_an_identical_non_matching_one():
    matching = summary("api-service", description="A backend service using PostgreSQL and Docker")
    non_matching = summary("frontend-widget", description="A small UI widget")

    ranked = rank_repositories(
        [non_matching, matching],
        top_n=2,
        relevance_terms=["postgresql", "docker"],
        reference_time=NOW,
    )

    assert ranked[0].name == "api-service"
    assert ranked[0].relevance_hits == ("postgresql", "docker")


def test_relevance_boost_uses_word_boundaries_not_substrings():
    # "ai" must not match inside "container" -- same guard as features/ml.py.
    repo = summary("containerized-app", description="Fully containerized deployment")

    result = score_repository(repo, relevance_terms=["ai"], reference_time=NOW)

    assert result.relevance_hits == ()


def test_ranking_without_relevance_terms_is_identical_to_stage_one_only():
    repos = [summary(f"repo-{i}", size_kb=100 * i) for i in range(5)]

    without_terms = rank_repositories(repos, top_n=5, relevance_terms=None, reference_time=NOW)
    with_empty_terms = rank_repositories(repos, top_n=5, relevance_terms=[], reference_time=NOW)
    default_call = rank_repositories(repos, top_n=5, reference_time=NOW)

    assert [r.score for r in without_terms] == [r.score for r in with_empty_terms] == [r.score for r in default_call]


def test_relevance_terms_never_help_a_repository_that_would_otherwise_be_excluded_replace_a_strong_original():
    # The boost is multiplicative on top of Stage 1, not a replacement --
    # a trivial fork mentioning the right word still shouldn't beat solid
    # unrelated original work by a wide margin.
    trivial_match = summary("fork-mentions-postgres", is_fork=True, size_kb=2, description="postgresql experiment")
    strong_unrelated = summary("real-project", size_kb=1500, description="A substantial original project")

    ranked = rank_repositories(
        [trivial_match, strong_unrelated],
        top_n=2,
        relevance_terms=["postgresql"],
        reference_time=NOW,
    )

    assert ranked[0].name == "real-project"
