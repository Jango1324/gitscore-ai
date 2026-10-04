"""Milestone 8A -- HTTP-level tests for `gitscore.api`.

All offline via FastAPI's `TestClient` -- the `get_github_client`
dependency is overridden with the existing `FakeEvidenceGitHubClient`
test double (`tests/conftest.py`), never a real network call.
`raise_server_exceptions=False` throughout so a 500 from the catch-all
handler is inspected as a normal response instead of re-raised by the
test client (Starlette's own debug-visibility behavior for the bare
`Exception` handler -- not relevant to what a real deployed caller
receives).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from conftest import FakeEvidenceGitHubClient, raw_repo, root_entry

from gitscore.api.app import app
from gitscore.api.routes import get_github_client
from gitscore.github.exceptions import (
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubRequestError,
)

BACKEND_JD = """Backend Software Engineer

Requirements:
- 3+ years of experience building Python backend services
- Experience with PostgreSQL
- Familiarity with Docker
- Excellent written and verbal communication

Preferred Qualifications:
- Experience with AWS
- Experience with Next.js
"""

ML_JD = """Machine Learning Engineer

Requirements:
- Expert-level Python
- Deep experience with PyTorch
- 5+ years of professional software engineering experience
- Experience with Docker or Kubernetes
"""

ZERO_ASSESSABLE_JD = """Requirements:
- 3+ years of professional experience required
- Bachelor degree in Computer Science required
- Excellent communication and leadership skills
"""


def _trivial_repo(name):
    return raw_repo(name=name, description=None, language=None, stargazers_count=0)


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_github_client, None)


def _use_fake_client(fake_client):
    app.dependency_overrides[get_github_client] = lambda: fake_client


def _backend_client_with_python_and_docker():
    return FakeEvidenceGitHubClient(
        repos=[_trivial_repo("api-service")],
        languages={"api-service": {"Python": 9000, "Shell": 1000}},
        root_contents={"api-service": [root_entry("Dockerfile")]},
    )


# ---------------------------------------------------------------------------
# A: health
# ---------------------------------------------------------------------------


def test_health_endpoint(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# B/C: valid analyze request -- full response shape
# ---------------------------------------------------------------------------


def test_valid_analyze_request_returns_full_shape(client):
    _use_fake_client(_backend_client_with_python_and_docker())

    response = client.post(
        "/api/v1/analyze",
        json={"github_username": "octocat", "job_description": BACKEND_JD},
    )

    assert response.status_code == 200
    body = response.json()

    assert body["analysis"]["github_username"] == "octocat"
    assert body["assessment"]["github_evidence_alignment"] == 40
    assert body["required"] == {"supported": 2, "assessable": 3}
    assert body["preferred"] == {"supported": 0, "assessable": 2}
    assert body["repository_analysis"] == {
        "discovered": 1,
        "analyzed": 1,
        "partially_analyzed": 0,
        "complete": True,
    }
    assert {r["text"] for r in body["requirements"]["supported"]} >= {"Familiarity with Docker"}
    assert len(body["requirements"]["not_observed"]) == 3
    assert len(body["requirements"]["not_assessable"]) == 2
    docker_match = next(r for r in body["requirements"]["supported"] if r["concept_id"] == "infra.docker")
    assert docker_match["evidence"][0]["repository"] == {"owner": "octocat", "name": "api-service"}
    assert body["diagnostics"] == {"extraction_failure_count": 0, "unknown_dependency_count": 0}
    assert body["versions"]["scoring"] == "github_evidence_alignment:v1"


def test_optional_job_title_and_company_pass_through(client):
    _use_fake_client(FakeEvidenceGitHubClient(repos=[]))

    response = client.post(
        "/api/v1/analyze",
        json={
            "github_username": "octocat",
            "job_description": BACKEND_JD,
            "job_title": "Backend Software Engineer",
            "job_company": "Example Corp",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["analysis"]["job_title"] == "Backend Software Engineer"
    assert body["analysis"]["job_company"] == "Example Corp"


# ---------------------------------------------------------------------------
# D/E/F: None -> JSON null, never 0/"N/A"/-1/fabricated SubscoreOut
# ---------------------------------------------------------------------------


def test_alignment_and_subscores_null_when_nothing_assessable(client):
    _use_fake_client(FakeEvidenceGitHubClient(repos=[]))

    response = client.post(
        "/api/v1/analyze",
        json={"github_username": "octocat", "job_description": ZERO_ASSESSABLE_JD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["assessment"]["github_evidence_alignment"] is None
    assert body["required"] is None
    assert body["preferred"] is None
    # Raw JSON text uses `null`, not a stringified sentinel.
    assert '"github_evidence_alignment":null' in response.text.replace(" ", "")


# ---------------------------------------------------------------------------
# G/H: NOT_OBSERVED / NOT_ASSESSABLE preserved
# ---------------------------------------------------------------------------


def test_not_observed_and_not_assessable_present_in_response(client):
    _use_fake_client(FakeEvidenceGitHubClient(repos=[_trivial_repo("unrelated")]))

    response = client.post(
        "/api/v1/analyze",
        json={"github_username": "octocat", "job_description": BACKEND_JD},
    )

    body = response.json()
    not_observed_statuses = {r["status"] for r in body["requirements"]["not_observed"]}
    not_assessable_statuses = {r["status"] for r in body["requirements"]["not_assessable"]}
    assert not_observed_statuses == {"not_observed"}
    assert not_assessable_statuses == {"not_assessable"}
    assert len(body["requirements"]["not_assessable"]) >= 1


# ---------------------------------------------------------------------------
# I: OR requirement preserved
# ---------------------------------------------------------------------------


def test_or_requirement_preserved(client):
    _use_fake_client(
        FakeEvidenceGitHubClient(
            repos=[_trivial_repo("training-repo")],
            root_contents={"training-repo": [root_entry("Dockerfile")]},
        )
    )

    response = client.post(
        "/api/v1/analyze",
        json={"github_username": "octocat", "job_description": ML_JD},
    )

    body = response.json()
    or_group = next(r for r in body["requirements"]["supported"] if len(r["alternative_concept_ids"]) > 1)
    assert or_group["matched_concept_ids"] == ["infra.docker"]


# ---------------------------------------------------------------------------
# J/K: evidence provenance and diagnostics preserved
# ---------------------------------------------------------------------------


def test_supporting_evidence_present_for_supported_requirements(client):
    _use_fake_client(_backend_client_with_python_and_docker())

    response = client.post(
        "/api/v1/analyze",
        json={"github_username": "octocat", "job_description": BACKEND_JD},
    )

    body = response.json()
    for requirement in body["requirements"]["supported"]:
        assert len(requirement["evidence"]) >= 1
    for requirement in body["requirements"]["not_observed"] + body["requirements"]["not_assessable"]:
        assert requirement["evidence"] == []


def test_extraction_diagnostics_preserved(client):
    _use_fake_client(
        FakeEvidenceGitHubClient(
            repos=[_trivial_repo("flaky")],
            languages_exc_for={"flaky": GitHubRequestError("boom", status_code=500)},
        )
    )

    response = client.post(
        "/api/v1/analyze",
        json={"github_username": "octocat", "job_description": BACKEND_JD},
    )

    body = response.json()
    assert body["diagnostics"]["extraction_failure_count"] == 1
    assert body["repository_analysis"]["partially_analyzed"] == 1


# ---------------------------------------------------------------------------
# L/M/N/O: transport-level input validation
# ---------------------------------------------------------------------------


def test_blank_username_rejected(client):
    response = client.post("/api/v1/analyze", json={"github_username": "   ", "job_description": BACKEND_JD})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_blank_job_description_rejected(client):
    response = client.post("/api/v1/analyze", json={"github_username": "octocat", "job_description": "   "})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_oversized_username_rejected(client):
    response = client.post(
        "/api/v1/analyze", json={"github_username": "x" * 40, "job_description": BACKEND_JD}
    )
    assert response.status_code == 422


def test_oversized_job_description_rejected(client):
    response = client.post(
        "/api/v1/analyze", json={"github_username": "octocat", "job_description": "x" * 20_001}
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# P/Q/R: GitHub-side failure -> HTTP mapping
# ---------------------------------------------------------------------------


def test_github_user_not_found_maps_to_404(client):
    _use_fake_client(FakeEvidenceGitHubClient(repos_exc=GitHubNotFoundError("no such user")))

    response = client.post(
        "/api/v1/analyze", json={"github_username": "ghost-user-xyz", "job_description": BACKEND_JD}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "github_user_not_found"


def test_github_rate_limit_maps_to_503_with_retry_after(client):
    _use_fake_client(FakeEvidenceGitHubClient(repos_exc=GitHubRateLimitError("rate limited", retry_after=42)))

    response = client.post("/api/v1/analyze", json={"github_username": "octocat", "job_description": BACKEND_JD})

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "github_rate_limited"
    assert body["error"]["retryable"] is True
    assert response.headers.get("retry-after") == "42"


def test_github_auth_configuration_error_maps_to_500(client):
    _use_fake_client(FakeEvidenceGitHubClient(repos_exc=GitHubRequestError("bad creds", status_code=401)))

    response = client.post("/api/v1/analyze", json={"github_username": "octocat", "job_description": BACKEND_JD})

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "github_auth_configuration_error"


def test_github_network_failure_maps_to_503(client):
    _use_fake_client(FakeEvidenceGitHubClient(repos_exc=GitHubRequestError("connection failed", status_code=None)))

    response = client.post("/api/v1/analyze", json={"github_username": "octocat", "job_description": BACKEND_JD})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "github_unavailable"


def test_github_upstream_5xx_exhausted_maps_to_502(client):
    _use_fake_client(FakeEvidenceGitHubClient(repos_exc=GitHubRequestError("upstream failure", status_code=500)))

    response = client.post("/api/v1/analyze", json={"github_username": "octocat", "job_description": BACKEND_JD})

    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "github_upstream_error"
    assert body["error"]["retryable"] is True


# ---------------------------------------------------------------------------
# S/T: unexpected internal failure sanitized, nothing leaked
# ---------------------------------------------------------------------------


def test_unexpected_internal_failure_is_sanitized(client, monkeypatch):
    import gitscore.api.routes as routes_module

    def boom(*args, **kwargs):
        raise RuntimeError("db password is s3cr3t; path=C:/Users/secret/.env")

    monkeypatch.setattr(routes_module, "analyze_job_fit", boom)

    response = client.post("/api/v1/analyze", json={"github_username": "octocat", "job_description": BACKEND_JD})

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "s3cr3t" not in response.text
    assert "RuntimeError" not in response.text
    assert "routes.py" not in response.text
    assert "Traceback" not in response.text


# ---------------------------------------------------------------------------
# U/V: calls analyze_job_fit exactly once, never rebuilds the pipeline
# ---------------------------------------------------------------------------


def test_analyze_job_fit_called_exactly_once(client, monkeypatch):
    import gitscore.api.routes as routes_module

    calls = []
    real = routes_module.analyze_job_fit

    def counting(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(routes_module, "analyze_job_fit", counting)
    _use_fake_client(_backend_client_with_python_and_docker())

    response = client.post("/api/v1/analyze", json={"github_username": "octocat", "job_description": BACKEND_JD})

    assert response.status_code == 200
    assert len(calls) == 1


def test_routes_module_never_imports_domain_stage_functions():
    """The endpoint must call `analyze_job_fit()` ONLY -- never
    `parse_job_description`/`match_job`/`assess_job`/
    `extract_candidate_evidence` directly (that would duplicate
    orchestration already owned by `gitscore.application`). Checked
    against the module's actual bound names (not a raw text/docstring
    grep), so mentioning one of these names in prose doesn't false-fail.
    """
    import gitscore.api.routes as routes_module

    forbidden_names = {"parse_job_description", "match_job", "assess_job", "extract_candidate_evidence"}
    assert forbidden_names.isdisjoint(vars(routes_module).keys())


# ---------------------------------------------------------------------------
# W: deterministic serialization
# ---------------------------------------------------------------------------


def test_identical_requests_produce_identical_responses(client):
    _use_fake_client(_backend_client_with_python_and_docker())
    response_a = client.post("/api/v1/analyze", json={"github_username": "octocat", "job_description": BACKEND_JD})

    _use_fake_client(_backend_client_with_python_and_docker())
    response_b = client.post("/api/v1/analyze", json={"github_username": "octocat", "job_description": BACKEND_JD})

    assert response_a.json() == response_b.json()
