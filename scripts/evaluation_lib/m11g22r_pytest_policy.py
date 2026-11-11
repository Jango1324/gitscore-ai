"""Milestone 11-G22-R -- pytest plugin: run an existing test session under one G22-R research policy.

    M11G22R_POLICY=D_alias_metadata_split python -m pytest -p m11g22r_pytest_policy tests/...

Used only by `scripts/evaluate_m11g22r_alias_evidence.py` to measure which EXISTING deterministic
tests a policy would break (regression risk). Never used by the normal test suite.
"""
from __future__ import annotations

import os

_ctx = None


def pytest_configure(config):
    global _ctx
    import m11g22r_policies as rpol
    name = os.environ["M11G22R_POLICY"]
    policy = next(p for p in rpol.POLICIES if p.name == name)
    _ctx = rpol.applied(policy)
    _ctx.__enter__()


def pytest_unconfigure(config):
    if _ctx is not None:
        _ctx.__exit__(None, None, None)
