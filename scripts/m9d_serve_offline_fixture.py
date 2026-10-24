"""Milestone 9D -- product-validation-only offline API server.

NOT a deliverable product feature. Serves the REAL FastAPI app
(`gitscore.api.app`) and the REAL orchestration entry point
(`gitscore.application.analyze_job_fit`) over HTTP, but injects a
`get_github_client` dependency override backed by one of this
evaluation corpus's own offline candidate fixtures
(`evaluation/fixtures/candidates/*.json`), via the exact same
`FakeCandidateGitHubClient` helper `scripts/evaluate_end_to_end.py`
already uses for Layers C/D. No live GitHub call is ever made.

This exists ONLY so the M9D workflow audit (docs/evaluation/
MILESTONE_9D_PRODUCT_VALIDATION.md, Phase 3) can exercise the actual
frontend against the actual API end to end, with the frontend dev
server's `NEXT_PUBLIC_GITSCORE_API_URL` pointed at this process,
without spending real GitHub API quota or needing network access.

Any `github_username` the frontend form submits is IGNORED for
repository lookup -- the single fixture passed on the command line is
always what's returned, regardless of the username typed. This is a
one-fixture-per-process harness, not a multi-tenant stand-in for
GitHub.

Usage:
    python scripts/m9d_serve_offline_fixture.py <candidate_fixture_name> [--port 8000]

Example:
    python scripts/m9d_serve_offline_fixture.py torvalds
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from evaluation_lib.loaders import EvaluationFixtureError, build_fake_client, load_candidate_fixture


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture_name", help="e.g. torvalds, karpathy, sindresorhus, Jango1324")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    try:
        fixture = load_candidate_fixture(args.fixture_name)
    except EvaluationFixtureError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    fake_client = build_fake_client(fixture)

    from gitscore.api.app import app
    from gitscore.api.routes import get_github_client

    app.dependency_overrides[get_github_client] = lambda: fake_client

    print(f"Serving offline fixture {args.fixture_name!r} on http://127.0.0.1:{args.port}")
    print("Every analyze request will use this fixture's evidence regardless of the username submitted.")

    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
