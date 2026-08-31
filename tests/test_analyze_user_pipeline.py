"""
End-to-end tests for gitscore.pipeline.analyze.analyze_user() (Milestone 3).

These test at the application-pipeline level, mocking only the two
external boundaries analyze_user() actually crosses:
- GitHub (gitscore.pipeline.analyze.GitHubClient is replaced with
  tests/conftest.py::FakeGitHubClient via
  tests/conftest.py::fake_github_client_factory)
- persistence (gitscore.pipeline.analyze.save_user /
  .save_profile_features are replaced with recording fakes)

No real network access, no GitHub token, and no writes to the real dev
database (data/gitscore.db) happen in this file.

Scenario coverage (see module docstring bullets in the milestone spec):
  A. normal user, full pipeline               -> test_normal_user_end_to_end
  B. zero repositories                        -> test_user_with_zero_repositories_completes_cleanly
  C. nonexistent GitHub user                   -> test_nonexistent_user_propagates_not_found_and_does_not_persist
  D. repository metadata degradation           -> test_repository_metadata_degradation_still_produces_a_profile
  E. rate limit during repository processing   -> already covered in
     tests/test_pipeline_repo_failure_handling.py::test_analyze_user_aborts_the_batch_when_a_worker_hits_a_rate_limit
     (Milestone 2); not duplicated here.
  F. persistence failure                       -> test_persistence_failure_surfaces_instead_of_returning_a_result
"""
import pytest

import gitscore.pipeline.analyze as analyze_module
from gitscore.github.exceptions import GitHubNotFoundError, GitHubRequestError
from conftest import FakeSavedUser, fake_github_client_factory, raw_repo


def patch_persistence(monkeypatch, save_user_impl=None, save_features_impl=None):
    """Monkeypatch save_user/save_profile_features with recording fakes
    (or caller-supplied implementations) and return the call-recording lists."""
    save_user_calls = []
    save_features_calls = []

    def default_save_user(data):
        save_user_calls.append(data)
        return FakeSavedUser(id=42)

    def default_save_features(user_id, features, score):
        save_features_calls.append((user_id, features, score))
        return object()

    monkeypatch.setattr(analyze_module, "save_user", save_user_impl or default_save_user)
    monkeypatch.setattr(analyze_module, "save_profile_features", save_features_impl or default_save_features)
    return save_user_calls, save_features_calls


# --- A. Normal user: full pipeline, result shape -------------------------

def test_normal_user_end_to_end(monkeypatch):
    repos = [raw_repo("proj-one"), raw_repo("proj-two")]
    factory = fake_github_client_factory(
        user={"login": "octocat", "name": "The Octocat", "followers": 10, "public_repos": 2},
        repos=repos,
        languages={"Python": 100},
        readme="# Hello\n## Installation\n## Usage",
    )
    monkeypatch.setattr(analyze_module, "GitHubClient", factory)
    save_user_calls, save_features_calls = patch_persistence(monkeypatch)

    result = analyze_module.analyze_user("octocat")

    # Public result shape
    assert set(result.keys()) == {"user", "features", "score", "time"}
    assert isinstance(result["features"], dict)
    assert isinstance(result["score"], dict)
    assert isinstance(result["time"], float)

    assert result["user"].id == 42
    assert result["features"]["total_repos"] == 2
    assert result["score"]["total_score"] == (
        result["score"]["ml_experience"]
        + result["score"]["project_originality"]
        + result["score"]["documentation_quality"]
        + result["score"]["language_tool_relevance"]
        + result["score"]["community_signal"]
    )

    # Both boundaries were actually exercised with the right data.
    assert save_user_calls == [{"login": "octocat", "name": "The Octocat", "followers": 10, "public_repos": 2}]
    assert len(save_features_calls) == 1
    assert save_features_calls[0][0] == 42  # saved_user.id
    assert save_features_calls[0][1] == result["features"]
    assert save_features_calls[0][2] == result["score"]


# --- B. Zero repositories --------------------------------------------------

def test_user_with_zero_repositories_completes_cleanly(monkeypatch):
    factory = fake_github_client_factory(
        user={"login": "newbie", "name": None, "followers": 0, "public_repos": 0},
        repos=[],
    )
    monkeypatch.setattr(analyze_module, "GitHubClient", factory)
    save_user_calls, save_features_calls = patch_persistence(monkeypatch)

    result = analyze_module.analyze_user("newbie")

    # Documented Milestone-1 empty-repo-list sentinel values (see
    # docs/ARCHITECTURE.md §5a) flow all the way through to a clean 0/100.
    assert result["features"]["total_repos"] == 0
    assert result["features"]["most_used_language"] == ""
    assert result["score"]["total_score"] == 0
    assert len(save_user_calls) == 1
    assert len(save_features_calls) == 1


# --- C. Nonexistent GitHub user --------------------------------------------

def test_nonexistent_user_propagates_not_found_and_does_not_persist(monkeypatch):
    factory = fake_github_client_factory(
        user_exc=GitHubNotFoundError("GitHub resource not found: /users/ghost")
    )
    monkeypatch.setattr(analyze_module, "GitHubClient", factory)
    save_user_calls, save_features_calls = patch_persistence(monkeypatch)

    with pytest.raises(GitHubNotFoundError):
        analyze_module.analyze_user("this-user-definitely-does-not-exist-123xyz")

    # No misleading data persisted for a user that was never actually found.
    assert save_user_calls == []
    assert save_features_calls == []


# --- D. Repository metadata degradation (Milestone 2 policy, at the ------
#        analyze_user() level rather than fetch_repo_data() in isolation)

def test_repository_metadata_degradation_still_produces_a_profile(monkeypatch):
    repos = [raw_repo("healthy-repo"), raw_repo("flaky-repo")]
    factory = fake_github_client_factory(
        user={"login": "octocat", "name": "Oct", "followers": 0, "public_repos": 2},
        repos=repos,
        languages={"Python": 100},
        languages_exc_for={"flaky-repo": GitHubRequestError("degraded", status_code=502)},
        readme="# readme",
        readme_exc_for={"flaky-repo": GitHubRequestError("degraded", status_code=500)},
    )
    monkeypatch.setattr(analyze_module, "GitHubClient", factory)
    save_user_calls, save_features_calls = patch_persistence(monkeypatch)

    result = analyze_module.analyze_user("octocat")

    # Both repos are still counted -- the flaky one degrades, it isn't dropped.
    assert result["features"]["total_repos"] == 2
    assert len(save_features_calls) == 1


# --- F. Persistence failure surfaces ---------------------------------------

def test_persistence_failure_surfaces_instead_of_returning_a_result(monkeypatch):
    factory = fake_github_client_factory(
        user={"login": "octocat", "name": "Oct", "followers": 0, "public_repos": 0},
        repos=[],
    )
    monkeypatch.setattr(analyze_module, "GitHubClient", factory)

    def failing_save_features(user_id, features, score):
        raise RuntimeError("simulated DB commit failure")

    save_user_calls, _ = patch_persistence(monkeypatch, save_features_impl=failing_save_features)

    with pytest.raises(RuntimeError, match="simulated DB commit failure"):
        analyze_module.analyze_user("octocat")

    # analyze_user() has no try/except around save_profile_features, so the
    # failure propagates instead of being swallowed into a result that
    # looks successful. Documented limitation: save_user() already
    # committed by this point (see docs/CHANGELOG_DEV.md Milestone 3 /
    # docs/PIPELINE.md Stage 5) -- there is no single transaction spanning
    # both persistence calls, so a user row can exist with no matching
    # feature snapshot if this happens against the real database.
    assert len(save_user_calls) == 1
