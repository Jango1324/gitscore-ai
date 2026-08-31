"""
Characterization tests for src/gitscore/github/client.py.

No real network calls are made: GitHubClient.session is replaced with a
scripted fake (see tests/conftest.py::ScriptedSession), so these tests
document the CURRENT request shape (pagination params, timeout) without
depending on GitHub's API or a token.

Milestone 2 (GitHub data collection reliability) fixed the three bugs
these tests originally pinned down (single-page-only fetching, no
timeout, no distinguishable rate-limit handling). They are rewritten
here to assert the corrected behavior instead of the old bug, per the
rule that a characterization test must not be kept green by preserving
a known defect. See tests/test_github_client_reliability.py for the
fuller pagination/retry/rate-limit test matrix added alongside this fix.
"""
import pytest

from gitscore.github.client import DEFAULT_TIMEOUT_SECONDS, GitHubClient
from gitscore.github.exceptions import GitHubRateLimitError
from tests.conftest import FakeResponse, ScriptedSession


def test_get_repositories_requests_with_explicit_pagination_params():
    """
    get_repositories() now sends explicit per_page/page query params on
    every page request, instead of relying on GitHub's undocumented
    default (per_page=30, page=1) and silently truncating any user with
    more repos than that.
    """
    client = GitHubClient(sleep_func=lambda seconds: None)
    fake_page = [{"name": f"repo-{i}"} for i in range(30)]
    client.session = ScriptedSession([FakeResponse(200, fake_page)])

    result = client.get_repositories("octocat")

    assert len(client.session.calls) == 1
    call = client.session.calls[0]
    params = call.get("params", {})
    assert params.get("per_page") == 100
    assert params.get("page") == 1
    assert result == fake_page


def test_requests_are_made_with_an_explicit_timeout():
    """
    Every GitHubClient request now passes an explicit `timeout=` to
    requests, so a stalled TCP connection can no longer block a worker
    thread indefinitely.
    """
    client = GitHubClient(sleep_func=lambda seconds: None)
    client.session = ScriptedSession([FakeResponse(200, [])])

    client.get_repositories("octocat")

    call = client.session.calls[0]
    assert call["timeout"] == DEFAULT_TIMEOUT_SECONDS


def test_get_user_raises_a_distinguishable_rate_limit_error():
    """
    A 403 carrying GitHub's rate-limit signal (X-RateLimit-Remaining: 0)
    now raises GitHubRateLimitError — a distinct, programmatically
    checkable type — instead of a bare Exception indistinguishable from
    "user not found" or "GitHub is down". The reset time is surfaced on
    the exception instead of being silently discarded.
    """
    client = GitHubClient(sleep_func=lambda seconds: None)
    client.session = ScriptedSession(
        [
            FakeResponse(
                403,
                {"message": "API rate limit exceeded"},
                headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1735689600"},
            )
        ]
    )

    with pytest.raises(GitHubRateLimitError) as excinfo:
        client.get_user("octocat")

    assert excinfo.value.reset_at == 1735689600
