"""
Tests for pipeline-level GitHub collection reliability (Milestone 2):
- individual optional repo metadata (languages/README) degrades
  gracefully after retries are exhausted, instead of failing the whole
  profile analysis
- a rate limit hit by any worker aborts the batch instead of being
  silently swallowed per-repo
- each ThreadPoolExecutor worker gets its own GitHubClient/session
  (thread-local), never a client shared/reused across threads

No network access, no GitHub token, and no real database writes:
GitHubClient and the db.queries functions imported into
gitscore.pipeline.analyze are monkeypatched with fakes.
"""
import threading

import pytest

import gitscore.pipeline.analyze as analyze_module
from gitscore.github.exceptions import GitHubRateLimitError, GitHubRequestError
from gitscore.pipeline.analyze import fetch_repo_data
from conftest import raw_repo


class StubClient:
    def __init__(self, languages_result=None, languages_exc=None, readme_result=None, readme_exc=None):
        self._languages_result = languages_result
        self._languages_exc = languages_exc
        self._readme_result = readme_result
        self._readme_exc = readme_exc

    def get_repository_languages(self, owner, repo):
        if self._languages_exc:
            raise self._languages_exc
        return self._languages_result

    def get_repository_readme(self, owner, repo_name):
        if self._readme_exc:
            raise self._readme_exc
        return self._readme_result


# --- fetch_repo_data: per-repo failure policy -----------------------------

def test_fetch_repo_data_degrades_gracefully_when_languages_fetch_fails_after_retries():
    client = StubClient(
        languages_exc=GitHubRequestError("boom", status_code=502),
        readme_result="# Hello",
    )

    result = fetch_repo_data(client, "octocat", raw_repo())

    assert result["languages"] == {}
    assert result["readme"] == "# Hello"


def test_fetch_repo_data_degrades_gracefully_when_readme_fetch_fails_after_retries():
    client = StubClient(
        languages_result={"Python": 100},
        readme_exc=GitHubRequestError("boom", status_code=500),
    )

    result = fetch_repo_data(client, "octocat", raw_repo())

    assert result["readme"] is None
    assert result["languages"] == {"Python": 100.0}


def test_fetch_repo_data_propagates_rate_limit_from_languages_instead_of_degrading():
    client = StubClient(languages_exc=GitHubRateLimitError("rate limited"))

    with pytest.raises(GitHubRateLimitError):
        fetch_repo_data(client, "octocat", raw_repo())


def test_fetch_repo_data_propagates_rate_limit_from_readme_instead_of_degrading():
    client = StubClient(languages_result={}, readme_exc=GitHubRateLimitError("rate limited"))

    with pytest.raises(GitHubRateLimitError):
        fetch_repo_data(client, "octocat", raw_repo())


# --- analyze_user: thread-local client design + batch-abort on rate limit --

class TrackingClient:
    """Fake GitHubClient recording which thread created/used each instance."""

    created = []

    def __init__(self, **kwargs):
        self.timeout = kwargs.get("timeout", 10.0)
        self.max_retries = kwargs.get("max_retries", 3)
        self.backoff_base = kwargs.get("backoff_base", 0.5)
        self.max_backoff = kwargs.get("max_backoff", 8.0)
        self.owner_thread = threading.get_ident()
        TrackingClient.created.append(self)

    def get_user(self, username):
        return {"login": username, "name": "Test", "followers": 0, "public_repos": 6}

    def get_repositories(self, username):
        return [raw_repo(f"repo-{i}") for i in range(6)]

    def get_repository_languages(self, owner, repo):
        assert threading.get_ident() == self.owner_thread
        return {}

    def get_repository_readme(self, owner, repo_name):
        assert threading.get_ident() == self.owner_thread
        return None


class FakeSavedUser:
    id = 1


def test_analyze_user_gives_each_worker_thread_its_own_client(monkeypatch):
    TrackingClient.created = []
    monkeypatch.setattr(analyze_module, "GitHubClient", TrackingClient)
    monkeypatch.setattr(analyze_module, "save_user", lambda data: FakeSavedUser())
    monkeypatch.setattr(
        analyze_module, "save_profile_features", lambda user_id, features, score: object()
    )

    result = analyze_module.analyze_user("octocat")

    # One client for the sequential get_user/get_repositories calls, plus
    # at most MAX_REPO_WORKERS more (one per worker thread that actually
    # ran a task) -- never one new client per repository.
    assert 1 < len(TrackingClient.created) <= 1 + analyze_module.MAX_REPO_WORKERS
    assert result["features"]["total_repos"] == 6
    assert result["score"] is not None


def test_analyze_user_aborts_the_batch_when_a_worker_hits_a_rate_limit(monkeypatch):
    class RateLimitedClient:
        def __init__(self, **kwargs):
            self.timeout = kwargs.get("timeout", 10.0)
            self.max_retries = kwargs.get("max_retries", 3)
            self.backoff_base = kwargs.get("backoff_base", 0.5)
            self.max_backoff = kwargs.get("max_backoff", 8.0)

        def get_user(self, username):
            return {"login": username, "name": "Test", "followers": 0, "public_repos": 1}

        def get_repositories(self, username):
            return [raw_repo("only-repo")]

        def get_repository_languages(self, owner, repo):
            raise GitHubRateLimitError("rate limited")

        def get_repository_readme(self, owner, repo_name):
            return None

    monkeypatch.setattr(analyze_module, "GitHubClient", RateLimitedClient)
    monkeypatch.setattr(analyze_module, "save_user", lambda data: FakeSavedUser())
    monkeypatch.setattr(
        analyze_module, "save_profile_features", lambda user_id, features, score: object()
    )

    with pytest.raises(GitHubRateLimitError):
        analyze_module.analyze_user("octocat")
