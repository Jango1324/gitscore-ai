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
from gitscore.assessment import SCORING_VERSION  # noqa: E402
from gitscore.evidence.capability import Capability, concept_capability  # noqa: E402
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
    # M11-G22-Q (v15) changes no G16 control (no compound control is an alias equivalence; measured
    # report delta v14 -> v15: none), so every v14 assertion below applies to v15 unchanged.
    assert parser_mod.JOB_DESCRIPTION_PARSER_VERSION in ("job_description_parser:v13", "job_description_parser:v14",
                                                         "job_description_parser:v15")
    v14 = parser_mod.JOB_DESCRIPTION_PARSER_VERSION in ("job_description_parser:v14", "job_description_parser:v15")
    if SCORING_VERSION == "github_evidence_alignment:v1":
        for cid, modes in report["results"].items():
            assert live["results"][cid]["production"] == modes["D_structural_guard"], cid
        assert live["metrics"]["production"] == report["metrics"]["D_structural_guard"]
        return
    # M11-G19 scoring v2: parsing and matching are unchanged, so rows,
    # statuses and matched concepts must still equal the frozen Option D
    # simulation exactly. Only the assessor's `assessable`/`score` may move,
    # and they must equal a v2 recomputation from the FROZEN statuses: a row
    # counts iff it was evaluated and every member is GitHub-assessable.
    assert SCORING_VERSION == "github_evidence_alignment:v2"
    scoring = ("assessable", "score")
    changed = set()
    for cid, modes in report["results"].items():
        frozen, got = modes["D_structural_guard"], live["results"][cid]["production"]
        if v14 and cid == "m11g16-053":
            # M11-G21: 053 ("You will maintain services ...", gold is_qualification=False) is now
            # declined by the qualification-intent guard instead of becoming a REQUIRED
            # not-assessable placeholder. It was never scored, so assessable/score are unchanged.
            assert [r["category"] for r in frozen["rows"]] == ["alternative_requirement"]
            assert got["rows"] == []
            for fx, f in frozen["fixtures"].items():
                g = got["fixtures"][fx]
                assert (g["statuses"], g["assessable"], g["score"]) == ([], 0, None), (cid, fx)
                assert (f["assessable"], f["score"]) == (0, None), (cid, fx)
            continue
        assert got["rows"] == frozen["rows"], cid
        for fx, f in frozen["fixtures"].items():
            g = got["fixtures"][fx]
            assert {k: v for k, v in g.items() if k not in scoring} == \
                {k: v for k, v in f.items() if k not in scoring}, (cid, fx)
            eligible = [i for i, s in enumerate(f["statuses"]) if s != "not_assessable" and all(
                concept_capability(m).capability == Capability.ASSESSABLE for m in frozen["rows"][i]["members"])]
            sup = sum(f["statuses"][i] == "supported" for i in eligible)
            expected = None if not eligible else (2 * 100 * sup + len(eligible)) // (2 * len(eligible))
            assert (g["assessable"], g["score"]) == (len(eligible), expected), (cid, fx)
            if (g["assessable"], g["score"]) != (f["assessable"], f["score"]):
                changed.add(cid)
    # 045 "Docker, Kubernetes or Terraform" (unresolved:terraform member) and
    # 058's fabricated unresolved:alternatively row -- exactly the two G18
    # predicted for the compound corpus.
    assert changed == {"m11g16-045", "m11g16-058"}
    for k, v in report["metrics"]["D_structural_guard"].items():
        if k == "4_false_declines_of_representable":
            # 045 is now not scored at all under v2 (its only row is excluded).
            assert set(live["metrics"]["production"][k]["ids"]) - set(v["ids"]) == {"m11g16-045"}
            assert set(v["ids"]) <= set(live["metrics"]["production"][k]["ids"])
        else:
            assert live["metrics"]["production"][k] == v, k


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
