"""
Characterization tests for src/gitscore/features/*.

These tests document the CURRENT behavior of the feature extractors.
As of Milestone 1 (feature correctness, see docs/CHANGELOG_DEV.md),
the description-coverage bug, the empty-repo-list crashes, and the
ML-keyword false positives previously pinned down here have all been
fixed. This file now asserts the corrected behavior instead of the old
bug, per the milestone instructions: do not keep a characterization
test green by preserving a known bug.

As of Milestone 3, the package itself was renamed from the misspelled
`feautures` to `features` (see docs/CHANGELOG_DEV.md) — imports below
reflect that.
"""
import pytest

from conftest import make_repo
from gitscore.features.quality import extract_quality_features
from gitscore.features.languages import extract_language_features
from gitscore.features.ml import extract_ml_features, ML_KEYWORDS
from gitscore.features.readme import extract_readme_features
from gitscore.features.activity import extract_activity_features


# ---------------------------------------------------------------------------
# quality.py: description_coverage_ratio
# ---------------------------------------------------------------------------

def test_description_coverage_ignores_blank_descriptions():
    """
    quality.py used to use `is not None or != ""`, which is always
    True, so every repo counted as "having a description" regardless
    of content. Fixed to `is not None and .strip() != ""`: a repo with
    an empty string or whitespace-only description no longer counts.
    """
    repos = [make_repo(description=""), make_repo(description="   "), make_repo(description=None)]
    features = extract_quality_features(repos)
    assert features["repositories_with_description"] == 0
    assert features["description_coverage_ratio"] == 0.0


def test_description_coverage_counts_real_descriptions():
    repos = [
        make_repo(description="A useful tool"),
        make_repo(description=""),
        make_repo(description=None),
    ]
    features = extract_quality_features(repos)
    assert features["repositories_with_description"] == 1
    assert features["description_coverage_ratio"] == pytest.approx(1 / 3)


# ---------------------------------------------------------------------------
# Empty repository list: no crashes, deterministic "no data" values
# ---------------------------------------------------------------------------

def test_quality_features_on_empty_repo_list_returns_zeros():
    """
    Previously raised ZeroDivisionError for a user with 0 public repos.
    Now returns 0 for every ratio/average, consistent with readme.py's
    existing empty-profile handling.
    """
    features = extract_quality_features([])
    assert features["total_stars"] == 0
    assert features["average_stars"] == 0
    assert features["total_forks"] == 0
    assert features["average_forks"] == 0
    assert features["repositories_with_description"] == 0
    assert features["description_coverage_ratio"] == 0


def test_language_features_on_empty_repo_list_returns_sentinel():
    """
    Previously raised ValueError from max() on an empty dict. Now
    returns unique_language_count=0 and most_used_language="" (the
    chosen "no language data available" sentinel — most_used_language
    is a non-nullable DB column, so None is not an option).
    """
    features = extract_language_features([])
    assert features["unique_language_count"] == 0
    assert features["most_used_language"] == ""
    assert features["python_repository_count"] == 0
    assert features["typescript_repository_count"] == 0
    assert features["has_python"] is False
    assert features["has_typescript"] is False


def test_language_features_sentinel_also_applies_when_repos_report_no_languages():
    """
    Same sentinel applies when repos exist but none report language
    data (e.g. every repo's `languages` dict is empty), not just when
    the repo list itself is empty.
    """
    features = extract_language_features([make_repo(languages={}), make_repo(languages={})])
    assert features["unique_language_count"] == 0
    assert features["most_used_language"] == ""


def test_readme_features_handle_empty_repo_list_gracefully():
    features = extract_readme_features([])
    assert features["readme_coverage_ratio"] == 0
    assert features["average_readme_length"] == 0


def test_activity_features_handle_empty_repo_list():
    features = extract_activity_features([])
    assert features["total_repos"] == 0
    assert features["original_repos"] == 0


def test_ml_features_handle_empty_repo_list():
    features = extract_ml_features([])
    assert features["ml_repository_count"] == 0
    assert features["ml_keyword_total"] == 0
    assert features["has_pytorch"] is False


# ---------------------------------------------------------------------------
# ml.py: keyword matching (word-boundary aware, no more raw substrings)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "name,description",
    [
        ("html-portfolio", "A static HTML/CSS site"),        # "ml" inside "html"
        ("explainer-app", "Explains a topic simply"),         # "ai" inside "explain"
        ("container-tools", "Docker container helpers"),      # "ai" inside "container"
        ("email-cleaner", "Cleans up your gmail inbox"),       # "ai" inside "email"/"gmail"
        ("maintainer-bot", "Helps maintain open source repos"),  # "ai" inside "maintain"
    ],
)
def test_ml_keyword_matching_no_longer_has_false_positives(name, description):
    """
    Previously: raw `word in text` substring search flagged these as
    ML repos. Now: word-boundary-aware matching requires the keyword to
    be a standalone token (bounded by non-alphanumeric characters), so
    none of these unrelated repos match.
    """
    repos = [make_repo(name=name, description=description)]
    features = extract_ml_features(repos)
    assert features["ml_repository_count"] == 0
    assert features["ml_keyword_total"] == 0


@pytest.mark.parametrize(
    "name,description",
    [
        ("ai-assistant", "An AI-powered helper"),
        ("ml-toolkit", "A small ML toolkit"),
        ("thesis-project", "Applies machine learning to genomics"),
        ("cv-pipeline", "Built with PyTorch"),
        ("nlp-app", "Uses TensorFlow for text classification"),
        ("data-tools", "Wrangles data with pandas and numpy"),
        ("scoring-model", "Trained with CatBoost"),
        ("chatbot", "Fine-tuned via HuggingFace transformers"),
        ("vision-app", "Built on OpenCV"),
        ("llm-app", "A wrapper around an LLM"),
        ("local-llm", "Runs models locally with Ollama"),
    ],
)
def test_ml_keyword_matching_true_positives_still_work(name, description):
    """
    All keywords in ML_KEYWORDS must still match when used as an actual
    standalone word/phrase, separated by spaces, hyphens, or punctuation.
    """
    repos = [make_repo(name=name, description=description)]
    features = extract_ml_features(repos)
    assert features["ml_repository_count"] == 1


@pytest.mark.parametrize("keyword", ML_KEYWORDS)
def test_every_declared_ml_keyword_matches_as_a_standalone_token(keyword):
    """Every entry in ML_KEYWORDS must match itself when it appears as
    a standalone word/phrase in a repo description."""
    repos = [make_repo(name="project", description=f"Uses {keyword} internally")]
    features = extract_ml_features(repos)
    assert features["ml_repository_count"] == 1


def test_ml_keyword_matching_underscore_and_hyphen_separated_tokens_match():
    """Hyphens/underscores act as separators, so glued-together tokens
    like "my-ai-project" and "llm_app" still match their keyword."""
    repos = [make_repo(name="my-ai-project", description="llm_app for experiments")]
    features = extract_ml_features(repos)
    assert features["ml_repository_count"] == 1
    assert features["ml_keyword_total"] == 2  # "ai" and "llm"


def test_ml_keyword_matching_flags_and_totals_are_consistent():
    repos = [
        make_repo(name="cv-pipeline", description="PyTorch + HuggingFace transformers"),
        make_repo(name="pandas-utils", description="Small pandas helpers"),
    ]
    features = extract_ml_features(repos)
    assert features["ml_repository_count"] == 2
    assert features["has_pytorch"] is True
    assert features["has_huggingface"] is True
    assert features["has_pandas"] is True
    assert features["has_catboost"] is False
    # distinct keywords found across the whole profile: pytorch, transformers, huggingface, pandas
    assert features["ml_keyword_total"] == 4
