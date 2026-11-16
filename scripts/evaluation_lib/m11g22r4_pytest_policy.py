"""Milestone 11-G22-R4 -- pytest plugin: run an existing test session under one R4 research README policy.

    M11G22R4_POLICY=P4_hybrid_overrides python -m pytest -p m11g22r4_pytest_policy tests/...

Used only by `scripts/evaluate_m11g22r4_high_recall_guard.py` to measure which EXISTING deterministic tests a README
occurrence policy would break. Nothing in `src/` imports it.
"""
from __future__ import annotations

import os

_ctx = None


def pytest_configure(config):
    global _ctx
    import m11g22r2_policies as p2
    import m11g22r4_policies as p4
    policy = next(p for p in (p2.A, *p4.CANDIDATES) if p.name == os.environ["M11G22R4_POLICY"])
    _ctx = p2.applied(policy)
    _ctx.__enter__()


def pytest_unconfigure(config):
    if _ctx is not None:
        _ctx.__exit__(None, None, None)
