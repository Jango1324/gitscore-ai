"""
Tests for src/gitscore/scoring/readiness.py (Milestone 3).

Per CLAUDE.md / the milestone instructions, these tests characterize the
CURRENT rubric exactly as implemented — they do not change weights or
thresholds. Every expected value below is hand-derived from the actual
if/elif ladders in readiness.py, not from the category-weight summary in
CLAUDE.md/ARCHITECTURE.md (those are cross-checked by the max-score
tests below, which confirm the implementation matches the documented
35/20/15/20/10 = 100 split).

No scoring bug was found while writing these tests: every category's
maximum matches its documented weight exactly, the five category scores
always sum to `total_score`, and `total_score` cannot exceed 100 for any
feature values observed in practice (verified with extreme inputs too).
"""
import pytest

from conftest import make_score_features
from gitscore.scoring.readiness import calculate_readiness_score


# ---------------------------------------------------------------------------
# Overall minimum / maximum
# ---------------------------------------------------------------------------

def test_all_zero_features_gives_zero_total_and_zero_every_category():
    """A brand-new/empty profile (Milestone 1's empty-repo-list sentinel
    values flow straight into this dict) must score a clean, unambiguous 0."""
    result = calculate_readiness_score(make_score_features())

    assert result["total_score"] == 0
    assert result["ml_experience"] == 0
    assert result["project_originality"] == 0
    assert result["documentation_quality"] == 0
    assert result["language_tool_relevance"] == 0
    assert result["community_signal"] == 0


def test_maximum_realistic_profile_scores_exactly_100():
    features = make_score_features(
        ml_repository_count=6,
        ml_keyword_total=6,
        original_repos=5,
        total_repos=5,
        readme_coverage_ratio=1.0,
        repositories_with_installation=3,
        repositories_with_usage=3,
        repositories_with_demo=3,
        repositories_with_badges=3,
        repositories_with_license=3,
        repositories_with_contributing=3,
        python_repository_count=5,
        has_pytorch=True,
        has_huggingface=True,
        has_pandas=True,
        has_catboost=True,
        total_stars=500,
        total_forks=10,
    )

    result = calculate_readiness_score(features)

    assert result["total_score"] == 100


@pytest.mark.parametrize(
    "overrides",
    [
        # Absurdly large counts must still be capped by the top bracket
        # of each ladder, not overflow past the category's documented max.
        dict(ml_repository_count=10_000, ml_keyword_total=10_000),
        dict(original_repos=10_000, total_repos=10_000),
        dict(readme_coverage_ratio=1.0, repositories_with_installation=10_000,
             repositories_with_usage=10_000, repositories_with_demo=10_000,
             repositories_with_badges=10_000, repositories_with_license=10_000,
             repositories_with_contributing=10_000),
        dict(python_repository_count=10_000, has_pytorch=True, has_huggingface=True,
             has_pandas=True, has_catboost=True),
        dict(total_stars=10_000_000, total_forks=10_000_000),
    ],
)
def test_total_score_cannot_exceed_100_for_extreme_inputs(overrides):
    features = make_score_features(**overrides)
    result = calculate_readiness_score(features)

    assert result["total_score"] <= 100


def test_all_categories_maxed_simultaneously_with_extreme_inputs_still_caps_at_100():
    features = make_score_features(
        ml_repository_count=999,
        ml_keyword_total=999,
        original_repos=999,
        total_repos=999,
        readme_coverage_ratio=1.0,
        repositories_with_installation=999,
        repositories_with_usage=999,
        repositories_with_demo=999,
        repositories_with_badges=999,
        repositories_with_license=999,
        repositories_with_contributing=999,
        python_repository_count=999,
        has_pytorch=True,
        has_huggingface=True,
        has_pandas=True,
        has_catboost=True,
        total_stars=999_999,
        total_forks=999_999,
    )

    result = calculate_readiness_score(features)

    assert result["total_score"] == 100


# ---------------------------------------------------------------------------
# Category scores always sum to total_score
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "overrides",
    [
        {},
        dict(ml_repository_count=2, ml_keyword_total=3, original_repos=2, total_repos=6,
             readme_coverage_ratio=0.4, python_repository_count=1, total_stars=7, total_forks=1),
        dict(ml_repository_count=5, ml_keyword_total=5, original_repos=5, total_repos=5,
             readme_coverage_ratio=1.0, repositories_with_installation=1,
             repositories_with_usage=1, repositories_with_demo=1, repositories_with_badges=1,
             repositories_with_license=1, repositories_with_contributing=1,
             python_repository_count=4, has_pytorch=True, has_huggingface=True,
             has_pandas=True, has_catboost=True, total_stars=150, total_forks=5),
    ],
)
def test_category_scores_sum_exactly_to_total_score(overrides):
    features = make_score_features(**overrides)
    result = calculate_readiness_score(features)

    assert (
        result["ml_experience"]
        + result["project_originality"]
        + result["documentation_quality"]
        + result["language_tool_relevance"]
        + result["community_signal"]
        == result["total_score"]
    )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_calculate_readiness_score_is_deterministic():
    features = make_score_features(
        ml_repository_count=3, ml_keyword_total=2, original_repos=2, total_repos=4,
        readme_coverage_ratio=0.6, python_repository_count=2, total_stars=12, total_forks=2,
    )

    first = calculate_readiness_score(features)
    second = calculate_readiness_score(dict(features))  # fresh dict, same values

    assert first == second


# ---------------------------------------------------------------------------
# Category maxima match the documented weights (35 / 20 / 15 / 20 / 10)
# ---------------------------------------------------------------------------

def test_ml_experience_category_max_is_35():
    features = make_score_features(ml_repository_count=5, ml_keyword_total=5)
    assert calculate_readiness_score(features)["ml_experience"] == 35


def test_project_originality_category_max_is_20():
    features = make_score_features(original_repos=5, total_repos=5)
    assert calculate_readiness_score(features)["project_originality"] == 20


def test_documentation_quality_category_max_is_15():
    features = make_score_features(
        readme_coverage_ratio=1.0,
        repositories_with_installation=1,
        repositories_with_usage=1,
        repositories_with_demo=1,
        repositories_with_badges=1,
        repositories_with_license=1,
        repositories_with_contributing=1,
    )
    assert calculate_readiness_score(features)["documentation_quality"] == 15


def test_language_tool_relevance_category_max_is_20():
    features = make_score_features(
        python_repository_count=4, has_pytorch=True, has_huggingface=True,
        has_pandas=True, has_catboost=True,
    )
    assert calculate_readiness_score(features)["language_tool_relevance"] == 20


def test_community_signal_category_max_is_10():
    features = make_score_features(total_stars=100, total_forks=3)
    assert calculate_readiness_score(features)["community_signal"] == 10


# ---------------------------------------------------------------------------
# Boundary conditions around thresholds (parametrized over the exact
# if/elif ladders in readiness.py)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "ml_repository_count,expected_repo_score",
    [(0, 0), (1, 10), (2, 16), (3, 20), (4, 23), (5, 25), (6, 25), (1000, 25)],
)
def test_ml_experience_repo_count_ladder(ml_repository_count, expected_repo_score):
    features = make_score_features(ml_repository_count=ml_repository_count, ml_keyword_total=0)
    assert calculate_readiness_score(features)["ml_experience"] == expected_repo_score


@pytest.mark.parametrize(
    "ml_keyword_total,expected_keyword_score",
    [(0, 0), (1, 3), (2, 5), (3, 7), (4, 8), (5, 10), (6, 10), (1000, 10)],
)
def test_ml_experience_keyword_count_ladder(ml_keyword_total, expected_keyword_score):
    features = make_score_features(ml_repository_count=0, ml_keyword_total=ml_keyword_total)
    assert calculate_readiness_score(features)["ml_experience"] == expected_keyword_score


def test_project_originality_zero_total_repos_does_not_raise():
    """total_repos == 0 must force ratio to 0, not raise ZeroDivisionError."""
    features = make_score_features(original_repos=0, total_repos=0)
    result = calculate_readiness_score(features)
    assert result["project_originality"] == 0


@pytest.mark.parametrize(
    "original_repos,total_repos,expected_ratio_score",
    [
        (0, 100, 0),      # ratio 0.00 -> < 0.25
        (25, 100, 3),     # ratio 0.25 -> not < 0.25, < 0.5  branch
        (49, 100, 3),     # ratio 0.49 -> < 0.5
        (50, 100, 6),     # ratio 0.50 -> not < 0.5, < 0.75 branch
        (74, 100, 6),     # ratio 0.74 -> < 0.75
        (75, 100, 8),     # ratio 0.75 -> not < 0.75, < 0.9 branch
        (89, 100, 8),     # ratio 0.89 -> < 0.9
        (90, 100, 10),    # ratio 0.90 -> not < 0.9 -> top bracket
        (100, 100, 10),   # ratio 1.00
    ],
)
def test_project_originality_ratio_ladder_boundaries(original_repos, total_repos, expected_ratio_score):
    # Use original_repos capped at 5 equivalent by keeping count-score
    # component separately verified; isolate the ratio component by
    # reading total category score and subtracting the known count score.
    features = make_score_features(original_repos=original_repos, total_repos=total_repos)
    result = calculate_readiness_score(features)

    count_score = {0: 0, 1: 3, 2: 5, 3: 7, 4: 8}.get(original_repos, 10 if original_repos >= 5 else 0)
    assert result["project_originality"] - count_score == expected_ratio_score


@pytest.mark.parametrize(
    "original_repos,expected_count_score",
    [(0, 0), (1, 3), (2, 5), (3, 7), (4, 8), (5, 10), (6, 10)],
)
def test_project_originality_count_ladder(original_repos, expected_count_score):
    # total_repos == original_repos keeps ratio at 1.0 (top bracket, +10)
    # so we can isolate the count-score component by subtracting 10
    # (or 0 when total_repos is also 0).
    total_repos = original_repos if original_repos > 0 else 0
    features = make_score_features(original_repos=original_repos, total_repos=total_repos)
    result = calculate_readiness_score(features)

    ratio_score = 0 if total_repos == 0 else 10  # ratio is always 1.0 here
    assert result["project_originality"] - ratio_score == expected_count_score


@pytest.mark.parametrize(
    "readme_coverage_ratio,expected_coverage_score",
    [(0.0, 0), (0.24, 0), (0.25, 2), (0.49, 2), (0.5, 3), (0.74, 3), (0.75, 4), (0.89, 4), (0.9, 5), (1.0, 5)],
)
def test_documentation_coverage_ratio_ladder(readme_coverage_ratio, expected_coverage_score):
    features = make_score_features(readme_coverage_ratio=readme_coverage_ratio)
    assert calculate_readiness_score(features)["documentation_quality"] == expected_coverage_score


def test_documentation_usefulness_subscores_are_independent_flags():
    # Each of installation/usage/demo contributes +2 independently of count.
    only_installation = make_score_features(repositories_with_installation=5)
    only_usage = make_score_features(repositories_with_usage=1)
    only_demo = make_score_features(repositories_with_demo=1)
    all_three = make_score_features(
        repositories_with_installation=1, repositories_with_usage=1, repositories_with_demo=1
    )

    assert calculate_readiness_score(only_installation)["documentation_quality"] == 2
    assert calculate_readiness_score(only_usage)["documentation_quality"] == 2
    assert calculate_readiness_score(only_demo)["documentation_quality"] == 2
    assert calculate_readiness_score(all_three)["documentation_quality"] == 6


def test_documentation_professional_subscores():
    features = make_score_features(
        repositories_with_badges=1, repositories_with_license=1, repositories_with_contributing=1
    )
    # badges(+1) + license(+2) + contributing(+1) = 4, coverage_ratio=0 -> +0
    assert calculate_readiness_score(features)["documentation_quality"] == 4


@pytest.mark.parametrize(
    "python_repository_count,expected_python_score",
    [(0, 0), (1, 3), (2, 5), (3, 6), (4, 8), (5, 8), (1000, 8)],
)
def test_language_tool_python_count_ladder(python_repository_count, expected_python_score):
    features = make_score_features(python_repository_count=python_repository_count)
    assert calculate_readiness_score(features)["language_tool_relevance"] == expected_python_score


def test_language_tool_flags_are_independent():
    features = make_score_features(has_pytorch=True, has_huggingface=True, has_pandas=True, has_catboost=True)
    # 4 + 3 + 2 + 3 = 12
    assert calculate_readiness_score(features)["language_tool_relevance"] == 12


@pytest.mark.parametrize(
    "total_stars,expected_star_score",
    [(0, 0), (1, 2), (2, 2), (3, 3), (9, 3), (10, 4), (49, 4), (50, 5), (99, 5), (100, 6), (10_000, 6)],
)
def test_community_star_ladder(total_stars, expected_star_score):
    features = make_score_features(total_stars=total_stars)
    assert calculate_readiness_score(features)["community_signal"] == expected_star_score


@pytest.mark.parametrize(
    "total_forks,expected_fork_score",
    [(0, 0), (1, 2), (2, 3), (3, 4), (4, 4), (1000, 4)],
)
def test_community_fork_ladder(total_forks, expected_fork_score):
    features = make_score_features(total_forks=total_forks)
    assert calculate_readiness_score(features)["community_signal"] == expected_fork_score


# ---------------------------------------------------------------------------
# Representative low / medium / high profiles (hand-computed end to end)
# ---------------------------------------------------------------------------

def test_representative_low_profile():
    # 1 original repo out of 4 (ratio 0.25 -> 3, count 1 -> 3) = 6 originality,
    # everything else at its zero baseline.
    features = make_score_features(original_repos=1, total_repos=4, readme_coverage_ratio=0.1)
    result = calculate_readiness_score(features)

    assert result["ml_experience"] == 0
    assert result["project_originality"] == 6
    assert result["documentation_quality"] == 0
    assert result["language_tool_relevance"] == 0
    assert result["community_signal"] == 0
    assert result["total_score"] == 6


def test_representative_medium_profile():
    features = make_score_features(
        ml_repository_count=3, ml_keyword_total=3,             # 20 + 7 = 27
        original_repos=3, total_repos=5,                        # ratio 0.6 -> 6, count 3 -> 7 = 13
        readme_coverage_ratio=0.6,                               # coverage 3
        repositories_with_installation=1, repositories_with_demo=1,  # usefulness 4
        repositories_with_badges=1, repositories_with_contributing=1,  # professional 2
        python_repository_count=2,                               # 5
        has_pytorch=True, has_pandas=True,                       # 4 + 2 = 6
        total_stars=15, total_forks=2,                           # star 4, fork 3 = 7
    )
    result = calculate_readiness_score(features)

    assert result["ml_experience"] == 27
    assert result["project_originality"] == 13
    assert result["documentation_quality"] == 9
    assert result["language_tool_relevance"] == 11
    assert result["community_signal"] == 7
    assert result["total_score"] == 67


def test_representative_high_profile():
    features = make_score_features(
        ml_repository_count=6, ml_keyword_total=6,
        original_repos=5, total_repos=5,
        readme_coverage_ratio=0.95,
        repositories_with_installation=1, repositories_with_usage=1, repositories_with_demo=1,
        repositories_with_badges=1, repositories_with_license=1, repositories_with_contributing=1,
        python_repository_count=5,
        has_pytorch=True, has_huggingface=True, has_pandas=True, has_catboost=True,
        total_stars=150, total_forks=5,
    )
    result = calculate_readiness_score(features)

    assert result["ml_experience"] == 35
    assert result["project_originality"] == 20
    assert result["documentation_quality"] == 15
    assert result["language_tool_relevance"] == 20
    assert result["community_signal"] == 10
    assert result["total_score"] == 100
