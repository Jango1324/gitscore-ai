import sys
from datetime import datetime
from pathlib import Path

import pytest

# Allow running `pytest` without an editable install.
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def make_repo(**overrides):
    """Build a repo dict shaped like gitscore.github.parser.parse_repo output."""
    repo = {
        "name": "sample-repo",
        "description": "A sample repository",
        "primary_language": "Python",
        "languages": {"Python": 100.0},
        "stars": 0,
        "forks": 0,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "is_fork": False,
        "html_url": "https://github.com/user/sample-repo",
        "readme": None,
    }
    repo.update(overrides)
    return repo


def raw_repo(name="sample", **overrides):
    """Build a repo dict shaped like a raw GitHub API repo object (parse_repo input)."""
    repo = {
        "name": name,
        "description": "desc",
        "language": "Python",
        "stargazers_count": 1,
        "forks_count": 0,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "fork": False,
        "html_url": f"https://github.com/user/{name}",
    }
    repo.update(overrides)
    return repo


def make_score_features(**overrides):
    """Build a feature dict with every key scoring.readiness.calculate_readiness_score
    reads, defaulted to the "no evidence" baseline (all-zero/False) that
    every category scores as 0. Override individual keys per test.
    """
    features = {
        "ml_repository_count": 0,
        "ml_keyword_total": 0,
        "original_repos": 0,
        "total_repos": 0,
        "readme_coverage_ratio": 0,
        "repositories_with_installation": 0,
        "repositories_with_usage": 0,
        "repositories_with_demo": 0,
        "repositories_with_badges": 0,
        "repositories_with_license": 0,
        "repositories_with_contributing": 0,
        "python_repository_count": 0,
        "has_pytorch": False,
        "has_huggingface": False,
        "has_pandas": False,
        "has_catboost": False,
        "total_stars": 0,
        "total_forks": 0,
    }
    features.update(overrides)
    return features


class FakeResponse:
    """Stand-in for requests.Response used by GitHubClient tests."""

    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else []
        self.headers = headers or {}

    def json(self):
        return self._payload


class ScriptedSession:
    """Stand-in for requests.Session.

    Returns one pre-programmed item per call to .get() (a FakeResponse to
    return, or an exception instance to raise), in order, and records
    every call (url + kwargs) it received. Used instead of real HTTP so
    tests need no network access, no GitHub token, and no real waiting.
    """

    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        if not self._scripted:
            raise AssertionError("ScriptedSession ran out of scripted responses")
        item = self._scripted.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeGitHubClient:
    """Configurable fake GitHubClient for analyze_user()-level pipeline tests.

    Per-repo languages/README results and exceptions are keyed by repo
    name (`languages_exc_for` / `readme_exc_for`) so a single flaky repo
    can be simulated among otherwise-healthy ones.
    """

    def __init__(
        self,
        user=None,
        user_exc=None,
        repos=None,
        repos_exc=None,
        languages=None,
        languages_exc_for=None,
        readme=None,
        readme_exc_for=None,
    ):
        self.timeout = 10.0
        self.max_retries = 3
        self.backoff_base = 0.5
        self.max_backoff = 8.0
        self._user = user
        self._user_exc = user_exc
        self._repos = repos if repos is not None else []
        self._repos_exc = repos_exc
        self._languages = languages if languages is not None else {}
        self._languages_exc_for = languages_exc_for or {}
        self._readme = readme
        self._readme_exc_for = readme_exc_for or {}

    def get_user(self, username):
        if self._user_exc:
            raise self._user_exc
        return self._user

    def get_repositories(self, username):
        if self._repos_exc:
            raise self._repos_exc
        return self._repos

    def get_repository_languages(self, owner, repo):
        if repo in self._languages_exc_for:
            raise self._languages_exc_for[repo]
        return self._languages

    def get_repository_readme(self, owner, repo_name):
        if repo_name in self._readme_exc_for:
            raise self._readme_exc_for[repo_name]
        return self._readme


def fake_github_client_factory(**config):
    """Build a GitHubClient-shaped callable for monkeypatching
    gitscore.pipeline.analyze.GitHubClient.

    analyze_user() constructs a GitHubClient more than once (the main
    thread's client, plus one per worker thread via the thread-local
    lazy-init in get_thread_client()). This factory makes every one of
    those construction calls return the SAME configured
    FakeGitHubClient instance, ignoring whatever timeout/retry kwargs
    the pipeline forwards to worker-thread clients -- appropriate for
    tests that assert on pipeline *behavior*, not per-thread client
    identity (see test_pipeline_repo_failure_handling.py::TrackingClient
    for a fake that DOES track per-thread instances).
    """
    shared = FakeGitHubClient(**config)

    def factory(*args, **kwargs):
        return shared

    return factory


class FakeSavedUser:
    """Stand-in for the User ORM object save_user() returns."""

    def __init__(self, id=1):
        self.id = id


class RecordingSleep:
    """Fake sleep function: records requested durations, never actually waits."""

    def __init__(self):
        self.calls = []

    def __call__(self, seconds):
        self.calls.append(seconds)


# ---------------------------------------------------------------------------
# Dataset-layer helpers (Milestone 4)
# ---------------------------------------------------------------------------

# Every ProfileFeature value column, defaulted to the "no evidence" baseline.
# Override individual keys per test via `add_snapshot(..., **overrides)`.
PROFILE_FEATURE_DEFAULTS = {
    "total_repos": 0,
    "original_repos": 0,
    "forked_repos": 0,
    "unique_language_count": 0,
    "ml_repository_count": 0,
    "readme_coverage_ratio": 0.0,
    "most_used_language": "",
    "python_repository_count": 0,
    "typescript_repository_count": 0,
    "has_python": False,
    "has_typescript": False,
    "total_stars": 0,
    "average_stars": 0.0,
    "total_forks": 0,
    "average_forks": 0.0,
    "repositories_with_description": 0,
    "description_coverage_ratio": 0.0,
    "has_pytorch": False,
    "has_huggingface": False,
    "has_pandas": False,
    "has_catboost": False,
    "ml_keyword_total": 0,
    "repositories_with_readme": 0,
    "average_readme_length": 0.0,
    "repositories_with_installation": 0,
    "repositories_with_usage": 0,
    "repositories_with_demo": 0,
    "repositories_with_badges": 0,
    "repositories_with_license": 0,
    "repositories_with_contributing": 0,
    "readiness_score": 0,
}


class SnapshotDB:
    """A throwaway SQLite database with the real User/ProfileFeature schema.

    Bound to a temp file, never to the real dev database. `session_factory`
    is a `SessionLocal`-shaped callable that `build_dataset` accepts
    directly.
    """

    def __init__(self, session_factory, engine):
        self.session_factory = session_factory
        self._engine = engine

    def add_snapshot(self, username, *, collected_at=None, followers=0,
                     public_repos=0, **feature_overrides):
        """Insert one ProfileFeature row for `username` (creating the User on
        first use). Returns the new snapshot id.
        """
        from sqlalchemy import select

        from gitscore.db.models import ProfileFeature, User

        unknown = set(feature_overrides) - set(PROFILE_FEATURE_DEFAULTS)
        if unknown:
            raise AssertionError(f"unknown ProfileFeature field(s): {sorted(unknown)}")

        values = {**PROFILE_FEATURE_DEFAULTS, **feature_overrides}
        session = self.session_factory()
        try:
            user = session.scalar(select(User).where(User.github_username == username))
            if user is None:
                user = User(
                    github_username=username,
                    name=None,
                    followers=followers,
                    public_repos=public_repos,
                )
                session.add(user)
                session.flush()

            snapshot = ProfileFeature(
                user_id=user.id,
                collected_at=collected_at or datetime(2026, 1, 1, 0, 0, 0),
                **values,
            )
            session.add(snapshot)
            session.commit()
            return snapshot.id
        finally:
            session.close()


@pytest.fixture
def snapshot_db(tmp_path):
    """Fresh `SnapshotDB` per test. No connection to data/gitscore.db."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from gitscore.db.database import Base
    from gitscore.db import models  # noqa: F401  (register mappers on Base)

    engine = create_engine(f"sqlite:///{tmp_path / 'snapshots.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    try:
        yield SnapshotDB(factory, engine)
    finally:
        engine.dispose()
