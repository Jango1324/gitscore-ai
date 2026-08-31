"""
Tests for GitHub data collection reliability (Milestone 2):
- full repository pagination
- explicit HTTP timeouts
- bounded retry/backoff on transient failures
- distinguishable rate-limit handling

All HTTP is faked via tests/conftest.py::ScriptedSession /
tests/conftest.py::FakeResponse — no network access, no GitHub token,
and no real waiting (retry/backoff tests inject a RecordingSleep fake
instead of sleeping).
"""
import requests
import pytest

from gitscore.github.client import (
    DEFAULT_MAX_RETRIES,
    GitHubClient,
)
from gitscore.github.exceptions import (
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubRequestError,
)
from tests.conftest import FakeResponse, RecordingSleep, ScriptedSession


def make_client(scripted_responses, **kwargs):
    sleep = kwargs.pop("sleep_func", None) or RecordingSleep()
    client = GitHubClient(sleep_func=sleep, **kwargs)
    client.session = ScriptedSession(scripted_responses)
    return client, sleep


# --- Pagination -------------------------------------------------------

def test_pagination_fewer_than_one_page():
    """A user with fewer repos than per_page stops after a single call."""
    page = [{"name": f"repo-{i}"} for i in range(5)]
    client, _ = make_client([FakeResponse(200, page)])

    result = client.get_repositories("octocat", per_page=100)

    assert result == page
    assert len(client.session.calls) == 1


def test_pagination_exactly_one_full_page():
    """
    A page that exactly fills per_page must trigger one more request to
    confirm there's nothing left (GitHub gives no total count up front).
    That next page comes back empty, so exactly 2 calls are made and no
    duplicate/garbage data is appended.
    """
    full_page = [{"name": f"repo-{i}"} for i in range(3)]
    client, _ = make_client(
        [FakeResponse(200, full_page), FakeResponse(200, [])],
    )

    result = client.get_repositories("octocat", per_page=3)

    assert result == full_page
    assert len(client.session.calls) == 2
    assert client.session.calls[0]["params"] == {"per_page": 3, "page": 1}
    assert client.session.calls[1]["params"] == {"per_page": 3, "page": 2}


def test_pagination_multiple_pages_are_concatenated_in_order():
    page1 = [{"name": "a"}, {"name": "b"}]
    page2 = [{"name": "c"}, {"name": "d"}]
    page3 = [{"name": "e"}]  # shorter than per_page -> last page
    client, _ = make_client(
        [FakeResponse(200, page1), FakeResponse(200, page2), FakeResponse(200, page3)],
    )

    result = client.get_repositories("octocat", per_page=2)

    assert result == page1 + page2 + page3
    assert len(client.session.calls) == 3
    assert [c["params"]["page"] for c in client.session.calls] == [1, 2, 3]


def test_pagination_empty_repository_list():
    client, _ = make_client([FakeResponse(200, [])])

    result = client.get_repositories("octocat", per_page=100)

    assert result == []
    assert len(client.session.calls) == 1


def test_pagination_stops_instead_of_looping_forever():
    """
    A server bug that always returns a full page must not turn
    pagination into an infinite loop: max_pages bounds it and raises a
    clear error instead.
    """
    full_page = [{"name": "x"}, {"name": "y"}]
    client, _ = make_client(
        [FakeResponse(200, full_page) for _ in range(5)],
    )

    with pytest.raises(GitHubRequestError):
        client.get_repositories("octocat", per_page=2, max_pages=4)

    assert len(client.session.calls) == 4


# --- Timeouts -----------------------------------------------------------

def test_timeout_is_configurable_and_applied_to_every_call():
    client, _ = make_client([FakeResponse(200, {"login": "octocat"})], timeout=3.5)

    client.get_user("octocat")

    assert client.session.calls[0]["timeout"] == 3.5


# --- Retry / backoff on transient failures -------------------------------

def test_connection_error_is_retried_then_succeeds():
    client, sleep = make_client(
        [
            requests.exceptions.ConnectionError("boom"),
            FakeResponse(200, {"login": "octocat"}),
        ]
    )

    result = client.get_user("octocat")

    assert result == {"login": "octocat"}
    assert len(client.session.calls) == 2
    assert len(sleep.calls) == 1  # backed off exactly once before the retry


def test_timeout_error_is_retried_then_succeeds():
    client, sleep = make_client(
        [
            requests.exceptions.Timeout("timed out"),
            FakeResponse(200, {"login": "octocat"}),
        ]
    )

    result = client.get_user("octocat")

    assert result == {"login": "octocat"}
    assert len(sleep.calls) == 1


def test_server_5xx_is_retried_then_succeeds():
    client, sleep = make_client(
        [FakeResponse(503, {"message": "unavailable"}), FakeResponse(200, {"login": "octocat"})]
    )

    result = client.get_user("octocat")

    assert result == {"login": "octocat"}
    assert len(sleep.calls) == 1


def test_retries_are_bounded_and_raise_after_exhaustion():
    failures = [requests.exceptions.ConnectionError("boom")] * (DEFAULT_MAX_RETRIES + 1)
    client, sleep = make_client(failures)

    with pytest.raises(GitHubRequestError):
        client.get_user("octocat")

    # DEFAULT_MAX_RETRIES retries -> DEFAULT_MAX_RETRIES+1 total attempts
    assert len(client.session.calls) == DEFAULT_MAX_RETRIES + 1
    assert len(sleep.calls) == DEFAULT_MAX_RETRIES


def test_backoff_delays_grow_and_are_capped():
    failures = [requests.exceptions.ConnectionError("boom")] * DEFAULT_MAX_RETRIES
    client, sleep = make_client(failures + [FakeResponse(200, {"login": "octocat"})])

    client.get_user("octocat")

    assert sleep.calls == [
        min(client.backoff_base * (2 ** i), client.max_backoff) for i in range(DEFAULT_MAX_RETRIES)
    ]


def test_genuine_404_is_not_retried():
    client, sleep = make_client([FakeResponse(404, {"message": "Not Found"})])

    with pytest.raises(GitHubNotFoundError):
        client.get_user("ghost-user-does-not-exist")

    assert len(client.session.calls) == 1
    assert sleep.calls == []


def test_client_validation_error_is_not_retried():
    """A genuine 422 (e.g. malformed request) must fail fast, not retry."""
    client, sleep = make_client([FakeResponse(422, {"message": "Validation Failed"})])

    with pytest.raises(GitHubRequestError) as excinfo:
        client.get_repository_languages("octocat", "repo")

    assert excinfo.value.status_code == 422
    assert len(client.session.calls) == 1
    assert sleep.calls == []


def test_missing_readme_returns_none_without_raising():
    """A 404 on the README endpoint is an expected condition, not a failure."""
    client, _ = make_client([FakeResponse(404, {"message": "Not Found"})])

    result = client.get_repository_readme("octocat", "repo")

    assert result is None


# --- Rate limiting --------------------------------------------------------

def test_primary_rate_limit_raises_distinct_error_with_reset_time():
    client, sleep = make_client(
        [
            FakeResponse(
                403,
                {"message": "API rate limit exceeded"},
                headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1700000000"},
            )
        ]
    )

    with pytest.raises(GitHubRateLimitError) as excinfo:
        client.get_repositories("octocat")

    assert excinfo.value.reset_at == 1700000000
    # not retried / no infinite wait — raised immediately for the caller to handle
    assert len(client.session.calls) == 1
    assert sleep.calls == []


def test_secondary_rate_limit_raises_distinct_error_with_retry_after():
    client, sleep = make_client(
        [
            FakeResponse(
                403,
                {"message": "You have exceeded a secondary rate limit"},
                headers={"Retry-After": "30"},
            )
        ]
    )

    with pytest.raises(GitHubRateLimitError) as excinfo:
        client.get_user("octocat")

    assert excinfo.value.retry_after == 30
    assert sleep.calls == []


def test_429_is_treated_as_rate_limit():
    client, _ = make_client([FakeResponse(429, {"message": "Too Many Requests"})])

    with pytest.raises(GitHubRateLimitError):
        client.get_user("octocat")


def test_plain_403_without_rate_limit_signal_is_not_treated_as_rate_limit():
    """
    A 403 with none of GitHub's rate-limit headers (e.g. permission
    denied on a resource) must not be misreported as a rate limit.
    """
    client, sleep = make_client([FakeResponse(403, {"message": "Forbidden"})])

    with pytest.raises(GitHubRequestError) as excinfo:
        client.get_user("octocat")

    assert not isinstance(excinfo.value, GitHubRateLimitError)
    assert excinfo.value.status_code == 403
    assert sleep.calls == []  # a genuine 403 is a client error, not retried
