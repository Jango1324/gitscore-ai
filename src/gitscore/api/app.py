"""Milestone 8A -- FastAPI application assembly.

    HTTP request
        |
        v
    gitscore.api  (this package: transport shape only)
        |
        v
    gitscore.application.analyze_job_fit()   (Milestone 7C)
        |
        v
    pipeline / jobs / matching / assessment   (domain layers)

`gitscore.api` depends on `gitscore.application`; nothing in
`gitscore.application` or any domain package imports from `gitscore.api`
-- dependency direction stays one-way, same discipline
`gitscore.application` itself already applies to the layers below it.

Run locally: `uvicorn gitscore.api.app:app --reload` (from `src/` on the
path, e.g. via the project's editable install) or
`python -m gitscore.api.app`.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gitscore.api.errors import register_exception_handlers
from gitscore.api.routes import router

# Explicit local frontend dev origins -- deliberately not "*", and
# deliberately not combined with allow_credentials=True (no
# cookies/auth exist yet to protect). A simple, safe development
# default; revisit when a real frontend origin/environment exists.
_DEV_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


def create_app() -> FastAPI:
    app = FastAPI(
        title="GitScore AI API",
        summary="GitHub evidence vs. job-requirement analysis",
        version="1",
    )
    app.include_router(router)
    register_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_DEV_CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
