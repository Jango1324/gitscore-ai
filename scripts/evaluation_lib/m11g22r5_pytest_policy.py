"""Milestone 11-G22-R5 -- pytest plugin: run an existing test session under one R5 research README policy.

    M11G22R5_POLICY=D_S_setext_sections python -m pytest -p m11g22r5_pytest_policy tests/...

Used only by `scripts/evaluate_m11g22r5_attribution_readme.py` to measure which EXISTING deterministic tests a README
policy would break. Nothing in `src/` imports it.
"""
from __future__ import annotations

import os

_stack = []


def pytest_configure(config):
    import m11g22r2_policies as p2
    import m11g22r5_policies as p5
    policy = next(p for p in (p2.A, *p5.CANDIDATES, *p5.COMPARISON) if p.name == os.environ["M11G22R5_POLICY"])
    mech = p5.mechanism()
    mech.__enter__()
    ctx = p2.applied(policy)  # routed through p5's mechanism (incl. the D_S heading-index swap)
    ctx.__enter__()
    _stack.extend([mech, ctx])


def pytest_unconfigure(config):
    while _stack:
        _stack.pop().__exit__(None, None, None)
