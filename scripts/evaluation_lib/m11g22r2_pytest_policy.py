"""Milestone 11-G22-R2 -- pytest plugin: run an existing test session under one G22-R2 README policy.

    M11G22R2_POLICY=D_hybrid_use_frames python -m pytest -p m11g22r2_pytest_policy tests/...

Used only by `scripts/evaluate_m11g22r2_readme_context.py` to measure which EXISTING deterministic tests a README
occurrence policy would break. Policy E's profile reinterpretation is not an extractor patch and is not applied here.
"""
from __future__ import annotations

import os

_ctx = None


def pytest_configure(config):
    global _ctx
    import m11g22r2_policies as p2
    import m11g22r2_posthoc as ph
    policy = next(p for p in (*p2.POLICIES, *ph.POSTHOC) if p.name == os.environ["M11G22R2_POLICY"])
    _ctx = p2.applied(policy)
    _ctx.__enter__()


def pytest_unconfigure(config):
    if _ctx is not None:
        _ctx.__exit__(None, None, None)
