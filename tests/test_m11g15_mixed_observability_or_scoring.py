"""Milestone 11-G15 -- mixed-observability OR scoring integrity.

Evaluation-only. Production behaviour is measured by calling the real,
unmodified parser/matcher/assessor; policies B-D are simulations. These
tests pin integrity and reproducibility of the measurement; they never
assert defective production behaviour as a success.
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

import evaluate_m11g15_or_scoring as runner  # noqa: E402
import gold_integrity as gi  # noqa: E402
import m11g15_build_controls as builder  # noqa: E402
import m11g15_or_scoring as orsc  # noqa: E402

M11G15 = REPO_ROOT / "evaluation" / "m11g15"


@pytest.fixture(scope="module")
def controls():
    return orsc.load_frozen_controls()


# The committed G15 report is a FROZEN measurement of parser v12 (the
# version live when G15 ran). M11-G17 moved production to v13, so the
# property tests below validate that frozen research result, and
# test_report_is_reproducible checks the explicit v12-vs-v13 relationship.
G15_REPORT_PARSER_VERSION = "job_description_parser:v12"
K1 = "m11g15-K1"


@pytest.fixture(scope="module")
def report():
    return json.loads((M11G15 / "or_scoring_report.json").read_text(encoding="utf-8"))


def test_controls_match_portable_freeze():
    freeze = json.loads((M11G15 / "controls_hash_freeze.json").read_text(encoding="utf-8"))
    raw = (M11G15 / "or_scoring_controls.json").read_bytes()
    assert gi.sha256(gi.canonical_bytes(raw)) == freeze["sha256_lf_normalized"]
    assert freeze["canonical_contract"] == gi.CONTRACT


def test_controls_cover_every_required_case(controls):
    cases = {c["case"] for c in controls["controls"]}
    assert set("ABCDEFGHIJKLMNOP") <= cases
    categories = {e["category"] for c in controls["controls"] for cand in c["expected"].values() for e in cand.values()}
    assert categories == set(builder.CATEGORIES)


def test_expectations_follow_the_frozen_semantic_rule(controls):
    """Expected outcomes were derived from annotated facts by the written
    rule, never edited by hand to match production."""
    for c in controls["controls"]:
        for cand in c["candidates"]:
            for g in c["gold_requirements"]:
                assert c["expected"][cand["name"]][g["gid"]] == builder.expected_outcome(g, cand), c["id"]


def test_unrepresentable_categories_are_explicit(controls):
    unrepresentable = {e["category"] for c in controls["controls"] for cand in c["expected"].values()
                       for e in cand.values() if not e["match_status_representable"]}
    assert unrepresentable == {"partially_observable_no_positive_evidence", "structurally_ambiguous"}


def test_report_is_reproducible(report):
    """Under v12 the live run must reproduce the frozen report exactly.
    Under v13 (M11-G17) a live re-run may differ ONLY on K1 -- the one G15
    control M11-G16 identified as a mixed AND/OR flattening -- where the
    flattened row is now contained (never SUPPORTED); every other control
    and the frozen 8c re-score must be identical."""
    from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION
    live = json.loads(json.dumps(runner.run()))
    if JOB_DESCRIPTION_PARSER_VERSION == G15_REPORT_PARSER_VERSION:
        assert live == report
        return
    assert JOB_DESCRIPTION_PARSER_VERSION == "job_description_parser:v13"
    for cid, result in report["results"].items():
        if cid != K1:
            assert live["results"][cid] == result, cid
    assert live["frozen_8c_matrices"] == report["frozen_8c_matrices"]
    k1_live = live["results"][K1]["candidates"]["python_only"]["policies"]["A_production"]["per_gold"]["g1"]
    k1_v12 = report["results"][K1]["candidates"]["python_only"]["policies"]["A_production"]["per_gold"]["g1"]
    assert k1_v12["status"] == "supported"        # the v12 false SUPPORTED G15 measured
    assert k1_live["status"] != "supported"       # contained by v13
    assert live["results"][K1]["rows"][0]["category"] == "alternative_requirement"


def test_policy_a_score_equals_the_real_assessor(controls):
    # evaluate_control() asserts, per control and candidate, that the
    # simulated policy-A score and denominator equal assess_job()'s own.
    for c in controls["controls"]:
        orsc.evaluate_control(c)


def test_simulated_policy_properties(report):
    m = report["metrics"]
    for policy in ("B_exclude_unresolved_groups", "D_parser_unsafe_fallback"):
        assert m[policy]["2_false_not_observed"]["count"] == 0
        assert m[policy]["3_non_assessable_counted_in_denominator"]["count"] == 0
        assert m[policy]["9_denominator_unstable_across_candidates"]["count"] == 0
    assert m["C_partial_state"]["2_false_not_observed"]["count"] == 0
    assert m["C_partial_state"]["9_denominator_unstable_across_candidates"]["count"] > 0
    assert (m["B_exclude_unresolved_groups"]["4_positive_evidence_discarded"]["count"]
            > m["C_partial_state"]["4_positive_evidence_discarded"]["count"])
    # The nested AND/OR flattening is NOT fixed by any scoring policy.
    for policy in orsc.POLICIES:
        assert m[policy]["1_false_supported"]["ids"] == ["m11g15-K1/python_only/g1"]


def test_no_policy_changes_the_scoring_formula(report):
    for control in report["7_scores"].values():
        for scores in control.values():
            for value in scores.values():
                assert value is None or 0 <= value <= 100


def test_frozen_8c_matrices_v1_and_v1_1_share_pairs(report):
    v1, v11 = report["frozen_8c_matrices"]["8c:v1"], report["frozen_8c_matrices"]["8c:v1.1"]
    assert [p["scores"] for p in v1["pairs"]] == [p["scores"] for p in v11["pairs"]]


_ALLOWED = re.compile(r"^(?:note|tracked|private_inspected_not_independent|evaluation_jobs_8c_corpus|"
                      r"m10_tracked_sources|m11d|m11f|m11g5|m11g9|postings|rows|technical_rows|or_groups[a-z_]*|"
                      r"unsafe_alternative_fallback_rows|unresolved_requirement_fallback_rows|"
                      r"single_unresolved_concept_rows)$")


def _keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys(v)


def test_structure_frequency_is_aggregate_only():
    data = json.loads((M11G15 / "structure_frequency.json").read_text(encoding="utf-8"))
    for k in _keys(data):
        assert _ALLOWED.match(k), k
    for group in ("tracked", "private_inspected_not_independent"):
        for counts in data.get(group, {}).values():
            assert all(isinstance(v, int) for v in counts.values())


def test_no_production_change_and_no_production_import():
    assert subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "src"], cwd=REPO_ROOT).returncode == 0
    offenders = [str(p) for p in (REPO_ROOT / "src" / "gitscore").rglob("*.py")
                 if "m11g15" in p.read_text(encoding="utf-8")]
    assert offenders == []


def test_no_network_or_llm_usage():
    for rel in ("scripts/evaluation_lib/m11g15_build_controls.py", "scripts/evaluation_lib/m11g15_or_scoring.py",
                "scripts/evaluate_m11g15_or_scoring.py"):
        src = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for forbidden in ("openai", "anthropic", "import requests", "httpx", "urllib.request", "import socket"):
            assert forbidden not in src, (rel, forbidden)
