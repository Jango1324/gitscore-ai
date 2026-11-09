"""Milestone 11-G18 -- observability-aware score eligibility (evaluation-only).

Production is measured by calling the real, unmodified parser, matcher
and assessor; policies are simulated on the real `RequirementMatch`
results. These tests pin the integrity and reproducibility of that
measurement and the invariants the recommended contract satisfies. They
never assert a production defect as a success.
"""
from __future__ import annotations

import json
import random
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src", REPO_ROOT / "scripts", REPO_ROOT / "scripts" / "evaluation_lib"):
    sys.path.insert(0, str(_p))

import evaluate_m11g18_scoring_eligibility as runner  # noqa: E402
import gold_integrity as gi  # noqa: E402
import m11g18_build_controls as builder  # noqa: E402
import m11g18_eligibility as el  # noqa: E402
from gitscore.assessment.models import _round_half_up_percentage  # noqa: E402
from gitscore.concepts.models import TechnicalConcept  # noqa: E402
from gitscore.concepts.registry import ConceptRegistry, default_registry  # noqa: E402
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION, parse_job_description  # noqa: E402
from gitscore.matching import match_job  # noqa: E402
from m11g15_or_scoring import candidate_profile  # noqa: E402

M11G18 = REPO_ROOT / "evaluation" / "m11g18"
CONTRACT_POLICIES = ("B_prefix_exclusion", "C_capability_declared", "D_parser_fallback")


@pytest.fixture(scope="module")
def controls():
    return el.load_frozen_controls()["controls"]


@pytest.fixture(scope="module")
def report():
    return json.loads((M11G18 / "eligibility_report.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------ frozen controls
def test_controls_match_portable_freeze():
    freeze = json.loads((M11G18 / "controls_hash_freeze.json").read_text(encoding="utf-8"))
    raw = (M11G18 / "eligibility_controls.json").read_bytes()
    assert gi.sha256(gi.canonical_bytes(raw)) == freeze["sha256_lf_normalized"]
    assert freeze["canonical_contract"] == gi.CONTRACT


def test_control_inventory_covers_the_brief(controls):
    assert len(controls) == 26
    assert sum(len(c["candidates"]) * len(c["gold_requirements"]) for c in controls) == 106
    families = {c["family"] for c in controls}
    for required in ("aws_or_azure", "azure_or_gcp", "or_fully_assessable", "two_non_assessable",
                     "mixed_registered_and_language", "standalone_supported", "standalone_unsupported_tool",
                     "standalone_unregistered_language", "package_without_detector", "hardware_interfaces",
                     "non_technical_and_education", "duplicate_alternatives", "ambiguous_combination",
                     "multiple_independent", "g17_placeholder_interaction", "preferred_enumeration_unknown"):
        assert required in families, required
    assert {g["necessity"] for c in controls for g in c["gold_requirements"]} >= {"required", "preferred"}


def test_expectations_follow_the_frozen_rule(controls):
    for c in controls:
        for cand in c["candidates"]:
            assert c["expected"][cand["name"]] == {g["gid"]: builder.expected_contract(g, cand)
                                                   for g in c["gold_requirements"]}, c["id"]
            assert c["expected_scores"][cand["name"]] == builder.expected_scores(c["gold_requirements"], cand)


def test_report_is_reproducible(report):
    assert report["parser_version"] == JOB_DESCRIPTION_PARSER_VERSION == "job_description_parser:v13"
    assert json.loads(json.dumps(runner.run())) == report


# ----------------------------------------------------------------- capability
def test_every_registered_concept_has_a_declared_pathway():
    table = el.registry_capability_table()
    assert len(table) == len(default_registry().all_concepts())
    for cid, row in table.items():
        assert row["capability"] == el.ASSESSABLE and row["reasons"], cid
    # language.c has no README-safe alias; it is reachable only via structured sources.
    assert not any(r.startswith("readme_mention") for r in table["language.c"]["reasons"])


def test_registration_alone_does_not_make_a_concept_assessable():
    reg = ConceptRegistry((TechnicalConcept(concept_id="hardware.bus_x", display_name="Bus X",
                                            category="hardware_interface", aliases=()),))
    cap, reasons = el.concept_capability("hardware.bus_x", reg)
    assert cap == el.NOT_ASSESSABLE_CAP and "no extractor" in reasons[0]


def test_unresolved_ids_are_unresolved_without_a_declared_vocabulary():
    assert el.concept_capability("unresolved:azure")[0] == el.UNRESOLVED
    assert el.concept_capability("unresolved:elixir")[0] == el.UNRESOLVED
    vocab = frozenset({"elixir"})
    assert el.concept_capability("unresolved:elixir", language_vocabulary=vocab)[0] == el.ASSESSABLE
    assert el.concept_capability("unresolved:azure", language_vocabulary=vocab)[0] == el.NOT_ASSESSABLE_CAP


def test_b_and_c_declared_select_identical_rows_on_the_current_registry(report):
    assert report["b_equals_c_declared"] == {"g18": True, "g15": True}


# ---------------------------------------------------------- reproduced defects
def test_production_defects_are_reproduced(report):
    a = report["g18_controls"]["metrics_summary"]["A_production"]
    assert a["1_false_not_observed_counted"] == 27
    assert a["2_false_not_observed_where_truly_qualified"] == 13
    assert a["3_uncheckable_counted_in_denominator"] == 33
    g15 = report["g15_controls"]["metrics_summary"]["A_production"]
    assert (g15["1_false_not_observed_counted"], g15["2_false_not_observed_where_truly_qualified"]) == (12, 6)


# ------------------------------------------------------- contract invariants
@pytest.mark.parametrize("corpus", ["g18_controls", "g15_controls"])
@pytest.mark.parametrize("policy", CONTRACT_POLICIES)
def test_contract_removes_false_not_observed_and_keeps_counting_honest(report, corpus, policy):
    m = report[corpus]["metrics_summary"][policy]
    assert m["1_false_not_observed_counted"] == 0          # invariant 2
    assert m["7_duplicate_or_merged_counting"] == 0         # invariant 6
    assert m["10_necessity_differs_on_counted_row"] == 0    # invariant 9
    assert m["12_orphan_rows_counted"] == 0
    assert m["8_controls_with_candidate_dependent_eligible_set"] == 0   # invariant 5


def test_only_preexisting_parser_defects_keep_uncheckable_rows_in_the_score(report):
    """Invariant 1. The two remaining rows are control 25's narrative
    sentence, which the parser itself turns into REQUIRED Python/Docker
    rows (a pre-existing parser defect, out of scope)."""
    ids = report["g18_controls"]["metrics"]["C_capability_declared"]["3_uncheckable_counted_in_denominator"]["ids"]
    assert ids == ["m11g18-25/python_docker/g1", "m11g18-25/python_docker/g3"]
    assert report["g15_controls"]["metrics_summary"]["C_capability_declared"][
        "3_uncheckable_counted_in_denominator"] == 0


@pytest.mark.parametrize("corpus", ["g18_controls", "g15_controls"])
def test_positive_evidence_stays_visible_except_under_the_parser_fallback(report, corpus):
    m = report[corpus]["metrics_summary"]   # invariant 3
    assert m["C_capability_declared"]["4b_positive_evidence_visible_in_diagnostics"] == \
        m["A_production"]["4b_positive_evidence_visible_in_diagnostics"]
    assert m["D_parser_fallback"]["4b_positive_evidence_visible_in_diagnostics"] < \
        m["A_production"]["4b_positive_evidence_visible_in_diagnostics"]


def test_declared_contract_is_met_wherever_the_parser_represents_the_requirement(report, controls):
    """Invariant 4 + 11: every mismatch with the frozen declared contract is
    a pre-existing parser representation defect (13: bare 'C' becomes
    unresolved:c; 16: alias OR becomes a placeholder; 25: narrative)."""
    met = set(report["g18_controls"]["metrics"]["C_capability_declared"]["13_score_equals_declared_contract"]["ids"])
    missed = {f"{c['id']}/{k['name']}" for c in controls for k in c["candidates"]} - met
    assert {m.split("/")[0] for m in missed} == {"m11g18-13", "m11g18-16", "m11g18-25"}


def test_no_eligible_requirement_means_undefined_score(report):
    res = report["g18_controls"]["results"]
    for cid in ("m11g18-04", "m11g18-05", "m11g18-15", "m11g18-20"):   # invariant 12
        for cand in res[cid]["candidates"].values():
            assert cand["policies"]["C_capability_declared"]["score"] is None
            assert cand["policies"]["C_capability_declared"]["eligible"] == 0


def test_rejected_asymmetric_policy_is_candidate_dependent(report):
    assert report["g18_controls"]["metrics_summary"]["E_asymmetric_rejected"][
        "8_controls_with_candidate_dependent_eligible_set"] == 8


def test_eligibility_is_candidate_independent_under_random_evidence():
    text = ("Requirements:\n- Python\n- Experience with AWS or Azure\n- Python, Terraform, Docker\n"
            "- Experience with Elixir or Zig")
    profile = parse_job_description(text)
    pool = ["language.python", "cloud.aws", "infra.docker", "unresolved:elixir", "unresolved:zig"]
    rng = random.Random(18)
    seen = set()
    for _ in range(40):
        evidence = rng.sample(pool, rng.randint(0, len(pool)))
        matches = match_job(candidate_profile(evidence), profile).requirement_matches
        for policy in CONTRACT_POLICIES:
            seen.add((policy, tuple(el.policy_row(policy, m)["counted"] for m in matches)))
    assert len({k for k in seen if k[0] == "C_capability_declared"}) == 1


def test_scores_use_the_unchanged_production_formula(report):
    for corpus in ("g18_controls", "g15_controls"):     # invariant 11
        for res in report[corpus]["results"].values():
            for cand in res["candidates"].values():
                for p in cand["policies"].values():
                    if p["eligible"]:
                        assert p["score"] == _round_half_up_percentage(p["supported"], p["eligible"])
                    else:
                        assert p["score"] is None


def test_source_spans_are_exact(report):
    for corpus in ("g18_controls", "g15_controls"):     # invariant 10
        for res in report[corpus]["results"].values():
            assert all(r["span_exact"] for r in res["rows"])


# ---------------------------------------------------------------- history
def test_frozen_8c_counterfactual_changes_are_exactly_the_known_six(report):
    expected = ["Jango1324/embedded_firmware_01", "karpathy/frontend_01", "sindresorhus/frontend_01",
                "sindresorhus/robotics_controls_01", "torvalds/data_science_01", "torvalds/embedded_firmware_01"]
    for label in ("8c:v1", "8c:v1.1"):
        assert report["frozen_8c"][label]["pairs_changed_vs_production"]["C_capability_declared"] == expected


def test_compound_controls_gain_no_false_supported(report):
    cc = report["g16_g17_compound_controls"]
    assert cc["fixture_outcomes"] == 414
    assert {p: v["count"] for p, v in cc["false_supported"].items()} == {p: 7 for p in cc["false_supported"]}


_ALLOWED = re.compile(r"^(?:note|m11d|m11f|m11g5|m11g9|postings|rows_by_eligibility_reason|technical_rows|"
                      r"technical_rows_excluded_by_capability_contract|all_members_assessable|no_concept_mapping|"
                      r"not_observable|standalone|mixed_or_group|or_group_without_assessable_member)$")


def _keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys(v)


def test_private_aggregates_are_counts_only():
    path = M11G18 / "private_eligibility_aggregates.json"
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    for k in _keys(data):
        assert _ALLOWED.match(k), k
    for name, block in data.items():
        if name != "note":
            assert all(isinstance(v, int) for k, v in block.items() if k != "rows_by_eligibility_reason")


# ------------------------------------------------------------------- scope
def test_no_production_change_and_no_production_import():
    assert subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "src"], cwd=REPO_ROOT).returncode == 0
    assert [str(p) for p in (REPO_ROOT / "src" / "gitscore").rglob("*.py")
            if "m11g18" in p.read_text(encoding="utf-8")] == []


def test_no_network_or_llm_usage():
    for rel in ("scripts/evaluation_lib/m11g18_build_controls.py", "scripts/evaluation_lib/m11g18_eligibility.py",
                "scripts/evaluation_lib/m11g18_option_regression_probe.py",
                "scripts/evaluate_m11g18_scoring_eligibility.py"):
        src = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for forbidden in ("openai", "anthropic", "import requests", "httpx", "urllib.request", "import socket"):
            assert forbidden not in src, (rel, forbidden)
