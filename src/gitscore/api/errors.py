"""Milestone 8A -- GitHub/input exceptions -> HTTP error responses.

One structured error envelope for every non-2xx response
(`gitscore.api.schemas.ErrorResponse`) and one place that decides the
HTTP status/code/message for each exception type the domain pipeline
can actually raise -- see `gitscore.github.exceptions` (the real
hierarchy this maps) and `gitscore.application.job_fit` (the one
`ValueError` source for blank input that survives past Pydantic's own
transport-level validation).

Mapping intent, not guesswork:

- `GitHubNotFoundError` -- the candidate's GitHub account genuinely
  doesn't exist. A caller error -> 404, not retryable.
- `GitHubRateLimitError` -- GitScore's OWN server-side GitHub credential
  hit GitHub's rate limit. This is never the API caller's fault (they
  never talk to GitHub directly), so this is NOT modeled as "you are
  being rate limited" (429) -- it is modeled as "a dependency this
  request needs is temporarily exhausted" -> 503, retryable, with
  `Retry-After` set from whichever of `retry_after`/`reset_at` GitHub
  actually supplied.
- `GitHubRequestError` -- a grab-bag by design (see its own docstring):
  covers a non-retryable 4xx, a non-retryable 5xx whose retry budget was
  exhausted, AND a connection/timeout failure, under one exception type
  with only `status_code` (possibly `None`) to distinguish them. Rather
  than inventing new exception subclasses on the GitHub client purely
  for HTTP convenience (explicitly out of scope -- Milestone 8A Part 26),
  this module branches on the one signal that IS available:
    * `status_code in {401, 403}` -- GitScore's OWN GitHub credential is
      invalid/misconfigured, not a transient condition and not the
      caller's fault -> 500 (server configuration error), not retryable.
    * `status_code` in the client's own `RETRYABLE_STATUS_CODES` (the
      retry budget was exhausted against a repeatedly-5xx GitHub) -> 502
      (upstream returned a server error), retryable.
    * `status_code is None` -- a connection/timeout failure (never got a
      real HTTP response at all) -> 503 (upstream unreachable), retryable.
    * anything else (an unexpected non-retried 4xx, or the pipeline's own
      "unexpected payload"/pagination-abort guards, which also carry no
      status code... handled by the `None` case above) -> 502, not
      retryable.
- A bare `ValueError` (blank `username`/`job_description` that somehow
  reached `analyze_job_fit()` despite Pydantic's own validation, or any
  other domain `__post_init__` invariant) -> 422, not retryable. Pydantic's
  own `RequestValidationError` gets the identical envelope/code, so a
  caller never has to special-case "which kind of 422 is this."
- Anything else (a genuine bug) -> 500, sanitized: logged in full
  server-side, never echoed back (no stack trace, no exception message,
  no internals) to the caller.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from gitscore.api.schemas import ErrorDetail, ErrorResponse
from gitscore.github.client import RETRYABLE_STATUS_CODES
from gitscore.github.exceptions import (
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubRequestError,
)

logger = logging.getLogger(__name__)

# 401/403 on OUR OWN outbound GitHub request means GitScore's configured
# credential is bad -- never something the API caller can fix by retrying
# or by changing their request.
_AUTH_STATUS_CODES = frozenset({401, 403})


def _error_response(status_code: int, code: str, message: str, *, retryable: bool, headers=None) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=code, message=message, retryable=retryable))
    return JSONResponse(status_code=status_code, content=body.model_dump(), headers=headers)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(
            422, "invalid_request", "The request was invalid.", retryable=False
        )

    @app.exception_handler(ValueError)
    async def _handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
        # Our own ValueErrors (blank username/job_description, or a
        # domain __post_init__ invariant) describe only the malformed
        # input itself -- safe to echo back verbatim, no internals.
        return _error_response(422, "invalid_request", str(exc), retryable=False)

    @app.exception_handler(GitHubNotFoundError)
    async def _handle_not_found(request: Request, exc: GitHubNotFoundError) -> JSONResponse:
        return _error_response(
            404,
            "github_user_not_found",
            "The requested GitHub user could not be found.",
            retryable=False,
        )

    @app.exception_handler(GitHubRateLimitError)
    async def _handle_rate_limit(request: Request, exc: GitHubRateLimitError) -> JSONResponse:
        headers = None
        if exc.retry_after is not None:
            headers = {"Retry-After": str(exc.retry_after)}
        return _error_response(
            503,
            "github_rate_limited",
            "GitScore's GitHub API quota is temporarily exhausted. Please try again later.",
            retryable=True,
            headers=headers,
        )

    @app.exception_handler(GitHubRequestError)
    async def _handle_request_error(request: Request, exc: GitHubRequestError) -> JSONResponse:
        logger.warning("GitHub request error (status_code=%s): %s", exc.status_code, exc)
        if exc.status_code in _AUTH_STATUS_CODES:
            return _error_response(
                500,
                "github_auth_configuration_error",
                "GitScore could not authenticate with GitHub.",
                retryable=False,
            )
        if exc.status_code in RETRYABLE_STATUS_CODES:
            return _error_response(
                502,
                "github_upstream_error",
                "GitHub returned an unexpected error while retrieving candidate data.",
                retryable=True,
            )
        if exc.status_code is None:
            return _error_response(
                503,
                "github_unavailable",
                "GitHub is temporarily unreachable. Please try again later.",
                retryable=True,
            )
        return _error_response(
            502,
            "github_upstream_error",
            "GitHub returned an unexpected error while retrieving candidate data.",
            retryable=False,
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Full detail goes to the server log only -- never to the
        # caller (no stack trace, no exception text, no internal paths).
        logger.exception("Unexpected internal error handling %s %s", request.method, request.url.path)
        return _error_response(500, "internal_error", "An unexpected internal error occurred.", retryable=False)
