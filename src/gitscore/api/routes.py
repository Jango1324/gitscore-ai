"""Milestone 8A -- the `/api/v1` router.

Transport only: validate the request shape (`AnalyzeRequest`), call the
ONE existing orchestration entry point
(`gitscore.application.analyze_job_fit`) exactly once, serialize its
result (`gitscore.api.serialization`). No repository ranking, no
evidence extraction, no job parsing, no matching, no scoring logic
lives here or anywhere else in `gitscore.api` -- `analyze_job_fit()`
remains the single source of truth for orchestration.

Synchronous by design: `analyze_job_fit()` (and everything it calls --
`GitHubClient` is a plain blocking `requests.Session` user) is
synchronous code, not a coroutine. Both endpoints below are plain `def`,
not `async def` -- FastAPI's own documented mechanism for this exact
situation: a synchronous path-operation function is automatically run
in a worker thread pool, so a slow/blocking `analyze_job_fit()` call
never blocks the server's event loop. Nothing in the domain pipeline
(`GitHubClient`, `extract_candidate_evidence`, ...) was rewritten to be
async for this milestone.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from gitscore.api.schemas import AnalyzeRequest, AnalyzeResponse, HealthResponse
from gitscore.api.serialization import serialize_job_analysis_result
from gitscore.application import analyze_job_fit
from gitscore.github.client import GitHubClient

router = APIRouter(prefix="/api/v1")


def get_github_client() -> GitHubClient | None:
    """Dependency seam for test injection.

    Returns `None` in production, so `analyze_job_fit()` constructs its
    own real `GitHubClient()` -- this module never constructs one
    itself. Tests override this dependency
    (`app.dependency_overrides[get_github_client]`) to inject a fake
    client with zero network access, exactly as
    `tests/test_application_job_fit.py` already does one layer down.
    """
    return None


@router.get("/health", response_model=HealthResponse, summary="Process health check")
def health() -> HealthResponse:
    """Process liveness only -- no GitHub call, no database call."""
    return HealthResponse(status="ok")


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Analyze a GitHub candidate's evidence against a job description",
)
def analyze(
    request: AnalyzeRequest,
    client: GitHubClient | None = Depends(get_github_client),
) -> AnalyzeResponse:
    result = analyze_job_fit(
        request.github_username,
        request.job_description,
        client=client,
        job_title=request.job_title,
        job_company=request.job_company,
    )
    return serialize_job_analysis_result(result)
