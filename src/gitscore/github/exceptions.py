"""Custom exception types for the GitHub API client.

These exist so callers (the pipeline, scripts) can distinguish failure
modes programmatically instead of parsing an exception message string.
Kept intentionally flat — one base class plus three concrete cases that
map onto the decisions callers actually need to make (retry? skip this
repo? abort the whole run?).
"""


class GitHubError(Exception):
    """Base class for all GitHub API client errors."""


class GitHubNotFoundError(GitHubError):
    """The requested resource genuinely does not exist (HTTP 404).

    Not retried. For most callers this is an expected condition (e.g. a
    repository with no README), not a failure.
    """


class GitHubRateLimitError(GitHubError):
    """GitHub reported the primary or secondary rate limit was hit.

    Never retried automatically by GitHubClient (that could mean waiting
    an arbitrarily long time) — it is raised immediately so the caller
    can decide whether to wait, skip, or abort using `reset_at` /
    `retry_after` when GitHub supplied them.
    """

    def __init__(self, message, *, reset_at=None, retry_after=None):
        super().__init__(message)
        self.reset_at = reset_at
        self.retry_after = retry_after


class GitHubRequestError(GitHubError):
    """A GitHub request failed and was not (or could no longer be) retried.

    Covers genuine non-retryable client errors (a 4xx that isn't a 404 or
    a rate limit) as well as connection failures / timeouts / retryable
    5xx responses whose retry budget was exhausted.
    """

    def __init__(self, message, *, status_code=None):
        super().__init__(message)
        self.status_code = status_code
