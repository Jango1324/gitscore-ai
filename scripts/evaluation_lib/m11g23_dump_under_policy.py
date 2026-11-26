"""Milestone 11-G23 -- run the G22-Q version-neutral historical dump with a G23 policy active (research only).

    python m11g23_dump_under_policy.py <policy-name|none> <out.json> [--private]

`none` runs the unpatched production pipeline. Any other name installs that G23 policy through
`m11g23_harness.active()` and then runs `m11g22q_parser_dump.main()` unchanged, so every historical corpus,
the frozen 8c matrices, G13/G15/G16/G18 scoring, G20/G21/G22 controls, M10E-g3 and the counts-only private
aggregates are measured through the same real parser, matcher and scoring with only segmentation replaced.
Private postings never leave the process; the dump itself writes integer counts only.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
name, out = sys.argv[1], sys.argv[2]
private = "--private" in sys.argv
sys.argv = [sys.argv[0], str(REPO_ROOT), out] + (["--private"] if private else [])

import m11g22q_parser_dump as dump  # noqa: E402  (reads sys.argv at import time)
import m11g23_harness as hz  # noqa: E402
import m11g23_policies as pol  # noqa: E402

if name == "none":
    dump.main()
else:
    policy = next(p for p in pol.ALL_POLICIES if p.name == name)
    with hz.active(policy):
        dump.main()
