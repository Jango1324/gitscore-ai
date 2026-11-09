"""Milestone 11-G16 -- compound AND/OR requirement logic integrity.

Evaluation-only. Production is measured by calling the real, unmodified
parser/matcher/assessor; fix options are installed in memory only and
always restored. Tests pin integrity and reproducibility of the
measurement and the safety invariants the recommended option satisfies;
they never assert a production defect as a success.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src", REPO_ROOT / "scripts", REPO_ROOT / "scripts" / "evaluation_lib"):
    sys.path.insert(0, str(_p))

import evaluate_m11g16_compound_logic as runner  # noqa: E402
import gitscore.jobs.parsing.parser as parser_mod  # noqa: E402
import gold_integrity as gi  # noqa: E402
import m11g16_build_controls as builder  # noqa: E402
import m11g16_compound_logic as sim  # noqa: E402

M11G16 = REPO_ROOT / "evaluation" / "m11g16"


@pytest.fixture(scope="module")
def controls():
    return sim.load_frozen_controls()["controls"]


# The committed G16 report is a FROZEN measurement of parser v12, with
# options simulated on top of it. M11-G17 implemented Option D as parser
# v13, so re-running the simulation now measures v13 as "production" (and
# C's guard can no longer see the flat OR it decomposes). The property tests
# below therefore validate the frozen v12 research result, and
# test_report_is_reproducible checks the explicit v12-vs-v13 relationship.
G16_REPORT_PARSER_VERSION = "job_description_parser:v12"


@pytest.fixture(scope="module")
def report():
    return json.loads((M11G16 / "compound_logic_report.json").read_text(encoding="utf-8"))


def test_controls_match_portable_freeze():
    freeze = json.loads((M11G16 / "controls_hash_freeze.json").read_text(encoding="utf-8"))
    raw = (M11G16 / "compound_logic_controls.json").read_bytes()
    assert gi.sha256(gi.canonical_bytes(raw)) == freeze["sha256_lf_normalized"]
    assert freeze["canonical_contract"] == gi.CONTRACT


def test_control_inventory(controls):
    assert len(controls) >= 50
    assert len({c["family"] for c in controls}) == 20


def test_expectations_follow_the_frozen_derivation_rules(controls):
    for c in controls:
        source = {k: v for k, v in c.items() if k != "expected"}
        assert c["expected"] == builder.expected_for(source), c["id"]


def test_report_is_reproducible(report):
    """Under v12 the live run must reproduce the frozen report exactly.
    Under v13 (M11-G17 = Option D) the live production parser must
    reproduce, for every one of the 58 controls and every evidence
    fixture, exactly what the frozen report SIMULATED for Option D."""
    live = json.loads(json.dumps(runner.run()))
    if parser_mod.JOB_DESCRIPTION_PARSER_VERSION == G16_REPORT_PARSER_VERSION:
        assert live == report
        return
    assert parser_mod.JOB_DESCRIPTION_PARSER_VERSION == "job_description_parser:v13"
    for cid, modes in report["results"].items():
        assert live["results"][cid]["production"] == modes["D_structural_guard"], cid
    assert live["metrics"]["production"] == report["metrics"]["D_structural_guard"]


def test_simulation_always_restores_the_parser(controls):
    before = (parser_mod.classify_alternative_claim, parser_mod._requirements_from_claim)
    for mode in sim.MODES:
        sim.parse(controls[6]["text"], mode)
    assert (parser_mod.classify_alternative_claim, parser_mod._requirements_from_claim) == before


@pytest.mark.parametrize("invariant", [
    "1_C_alone_cannot_satisfy_(A_or_B)_and_C",
    "2_A_alone_cannot_satisfy_A_and_(B_or_C)",
    "3_A_and_C_may_satisfy_(A_or_B)_and_C",
    "4_distinct_alternatives_not_equivalent",
    "5_irrelevant_evidence_satisfies_nothing",
    "6_unevidenceable_never_positive",
    "8_stable_eligibility_across_candidates",
    "10_source_provenance_kept",
    "11_no_new_required_by_default",
    "12_simple_or_and_unchanged",
])
def test_recommended_option_satisfies_invariant(report, invariant):
    assert report["invariants"]["C_decompose"][invariant] is True


def test_recommended_option_reduces_false_supported_without_new_false_declines(report):
    m = report["metrics"]
    assert m["C_decompose"]["1_false_supported_claim_level"]["count"] < \
        m["production"]["1_false_supported_claim_level"]["count"]
    assert m["C_decompose"]["4_false_declines_of_representable"]["count"] <= \
        m["production"]["4_false_declines_of_representable"]["count"]
    assert m["C_decompose"]["3_genuine_represented_exactly"]["count"] > \
        m["production"]["3_genuine_represented_exactly"]["count"]


def test_frozen_8c_scores_unchanged_by_every_option(report):
    for matrix in report["frozen_8c_matrices_counterfactual"].values():
        assert all(not v for v in matrix["pairs_changed_vs_production"].values())


_ALLOWED = re.compile(r"^(?:note|m11d|m11f|m11g5|m11g9|texts|A_lexical_guard|D_structural_guard|C_decompose|"
                      r"texts_with_changed_rows|rows_production|rows_option)$")


def _keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys(v)


def test_private_aggregates_are_counts_only():
    path = M11G16 / "private_impact_aggregates.json"
    if not path.exists():
        return
    for k in _keys(json.loads(path.read_text(encoding="utf-8"))):
        assert _ALLOWED.match(k), k


def test_no_production_change_and_no_production_import():
    assert subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "src"], cwd=REPO_ROOT).returncode == 0
    assert [str(p) for p in (REPO_ROOT / "src" / "gitscore").rglob("*.py")
            if "m11g16" in p.read_text(encoding="utf-8")] == []


def test_no_network_or_llm_usage():
    for rel in ("scripts/evaluation_lib/m11g16_build_controls.py", "scripts/evaluation_lib/m11g16_compound_logic.py",
                "scripts/evaluation_lib/m11g16_option_regression_probe.py",
                "scripts/evaluate_m11g16_compound_logic.py"):
        src = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for forbidden in ("openai", "anthropic", "import requests", "httpx", "urllib.request", "import socket"):
            assert forbidden not in src, (rel, forbidden)
