"""Milestone 8A -- the HTTP transport layer.

Exposes `gitscore.application.analyze_job_fit()` over a thin FastAPI
API. Contains NO business logic of its own: no repository ranking, no
evidence extraction, no job parsing, no matching, no scoring -- see
`gitscore.api.routes` for the one place a request reaches the
application layer, and `gitscore.api.app`'s module docstring for the
full dependency-direction diagram.
"""
from gitscore.api.app import app

__all__ = ["app"]
