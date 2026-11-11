"""Milestone 11-G13 -- G12 generalization, OR-contract study, gold portability.

Evaluation-only. Synthetic G13 controls are original text by the same
author as G12 (NON-INDEPENDENT, disclosed in the frozen protocol). The
real-text track reads private holdouts locally and emits aggregates only.
No LLM, no production change, no G10/G11/G12 change.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src", REPO_ROOT / "scripts" / "evaluation_lib", REPO_ROOT / "scripts"):
    sys.path.insert(0, str(_p))

import evaluate_m11g12_validator_hardening as ev12  # noqa: E402
import evaluate_m11g13_generalization as ev13  # noqa: E402
import m11g10_competency_concept_model as g10  # noqa: E402
import m11g12_validator_hardening as g12  # noqa: E402
import m11g13_or_contract as orc  # noqa: E402
import m11g13_real_text_track as rtt  # noqa: E402
import test_m11g12_validator_hardening as g12_tests  # noqa: E402
from gitscore.jobs import GithubObservability, Importance, JobRequirement, Necessity  # noqa: E402
from gitscore.matching import MatchStatus, match_requirement  # noqa: E402

M11G13 = REPO_ROOT / "evaluation" / "m11g13"


@pytest.fixture(scope="module")
def graph():
    return g10.build_reference_graph()


@pytest.fixture(scope="module")
def report():
    return ev13.run()


@pytest.fixture(scope="module")
def controls():
    return ev13.load_frozen_controls()[0]


# ---------------------------------------------------------------------------
# Frozen protocol and controls
# ---------------------------------------------------------------------------


def test_controls_match_freeze_raw_or_lf_normalized():
    raw = (M11G13 / "generalization_controls.json").read_bytes()
    freeze = json.loads((M11G13 / "controls_hash_freeze.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == freeze["sha256_lf_normalized"]


def test_protocol_discloses_non_independence(controls):
    independence = controls["protocol"]["independence"]
    assert "NON-INDEPENDENT" in independence["synthetic_track"]
    assert "MECHANICALLY" in independence["real_text_track"]


def test_control_coverage(controls):
    rows = controls["controls"]
    scored = [c for c in rows if c["kind"] in ("necessity", "concept")]
    assert len(scored) >= 60
    nec_categories = {c["category"] for c in rows if c["kind"] == "necessity"}
    assert {
        "explicit_required", "explicit_preferred", "unknown_necessity", "negation", "cross_claim_contamination",
        "cross_sentence", "employer_narrative", "responsibility", "contradictory", "quoted_text", "prompt_injection",
        "conditional", "markdown_structure", "and_or_group", "ambiguous",
    } <= nec_categories
    con_categories = {c["category"] for c in rows if c["kind"] == "concept"}
    assert {"correct_mapping", "valid_id_wrong_concept", "multi_concept", "ambiguous_alias",
            "absent_from_ontology", "structurally_invalid"} <= con_categories
    assert sum(1 for c in rows if c["kind"] == "or_contract") >= 12
    for c in rows:
        s = c["span"]
        assert c["job_text"][s["start"]:s["end"]] == s["text"], c["id"]


def test_report_is_reproducible(report):
    committed = json.loads((M11G13 / "generalization_report.json").read_text(encoding="utf-8"))
    for volatile in ("controls_freeze_matched_by",):
        committed.pop(volatile, None)
        report = {k: v for k, v in report.items() if k != volatile}
    from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION
    if JOB_DESCRIPTION_PARSER_VERSION == "job_description_parser:v15":
        # M11-G22-Q (v15): o007 "Experience with Kubernetes or k8s" (gold: equivalent_aliases, one
        # scored requirement) is now ONE assessable infra.kubernetes row instead of a dropped
        # placeholder. These are the ONLY differences from the committed (v14) report; o012
        # "Docker or Docker Compose" (gold: related, non-equivalent) is deliberately unchanged.
        ref = committed["or_contract"]["production_reference"]
        ref["per_control"]["m11g13-o007"].update(assessable_rows=1, supported_rows=1, correct_satisfaction=True,
                                                 dropped_decidable_requirement=False)
        ok, dropped = ref["correct_satisfaction_on_decidable"], ref["dropped_decidable_requirements"]
        ok.update(count=ok["count"] + 1, ids=sorted(ok["ids"] + ["m11g13-o007"]))
        dropped.update(count=dropped["count"] - 1, ids=[i for i in dropped["ids"] if i != "m11g13-o007"])
        assert dropped["ids"] == ["m11g13-o008", "m11g13-o012"]
    assert json.loads(json.dumps(report)) == committed


# ---------------------------------------------------------------------------
# Phase 1 -- the four G12 known-unsafe cases stay visible
# ---------------------------------------------------------------------------


def test_g12_known_unsafe_cases_remain_declared():
    unsafe = [p for p in g12_tests.POST_FREEZE_PROBES if p[1] == "unsafe"]
    assert {p[0] for p in unsafe} == {"negation_beyond_window", "single_quoted_marker", "cue_free_injection_same_unit"}
    assert g12_tests.FROZEN_RESIDUAL_N055[1] == "unsafe"


def test_g12_concept_finding_unchanged():
    data = json.loads((REPO_ROOT / "evaluation" / "m11g12" / "before_after_report.json").read_text(encoding="utf-8"))
    finding = data["after_g12"]["concept"]["automatic_accepts_that_gold_marks_incorrect"]
    assert (finding["count"], finding["denominator"]) == (6, 10)


# ---------------------------------------------------------------------------
# Phase 3 -- G12 generalization failures on G13 controls (NOT fixed in G13)
# ---------------------------------------------------------------------------

G13_UNSAFE_ACCEPTANCES = (
    "m11g13-n026",  # elliptical negation "Kotlin is not" with the other clause's marker
    "m11g13-n030",  # n055 shape in new words
    "m11g13-n035",  # employee duty not caught by classification
    "m11g13-n037",  # onboarding obligation not caught by classification
    "m11g13-n038",  # "Responsibilities:" label not caught by classification
    "m11g13-n043",  # single-quoted, disavowed marker
    "m11g13-n044",  # bracketed instruction ("classify as required")
    "m11g13-n046",  # tool-generated default ("flags this as required")
    "m11g13-n047",  # temporal condition "once ..." not a known condition cue
    "m11g13-n049",  # "For the embedded track" condition not a known cue
    "m11g13-n050",  # "where the contract demands it" condition not a known cue
    "m11g13-n063",  # "required-ish" matches the word-boundary marker
)


@pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason="KNOWN UNSAFE G12 generalization failure on independent-phrasing G13 controls; "
           "measured, not fixed, in M11-G13.",
)
@pytest.mark.parametrize("control_id", G13_UNSAFE_ACCEPTANCES)
def test_g12_should_decline_g13_unsupported_necessity(controls, graph, control_id):
    c = next(x for x in controls["controls"] if x["id"] == control_id)
    r = g12.validate_candidate_hardened(ev12.build_candidate(c), c["job_text"], graph)
    assert r.necessity.value == c["expected_validator_necessity"] or not r.accepted_for_review


def test_unsafe_list_matches_measurement(report):
    measured = report["after_g12"]["necessity"]["all_unsafe_necessity_acceptances"]["ids"]
    assert sorted(measured) == sorted(G13_UNSAFE_ACCEPTANCES)


# ---------------------------------------------------------------------------
# Phase 4/5 -- OR contract
# ---------------------------------------------------------------------------


def _row(**kw):
    return JobRequirement(original_text="x", necessity=Necessity.REQUIRED, importance=Importance.MEDIUM,
                          github_observability=GithubObservability.STRONGLY_OBSERVABLE, **kw)


def test_production_or_semantics_reference():
    profile = orc.candidate_profile(["infra.docker"])
    group = _row(alternative_concept_ids=("infra.docker", "infra.kubernetes"))
    assert match_requirement(group, profile).status == MatchStatus.SUPPORTED  # either alternative satisfies
    k8s = _row(concept_id="infra.kubernetes")
    assert match_requirement(k8s, profile).status == MatchStatus.NOT_OBSERVED  # Docker never proves Kubernetes


def test_or_strategy_safety_properties(report):
    r = report["or_contract"]
    c, b, a = r["C_separate_grouping"], r["B_distinct_members_in_g11_field"], r["A_equivalent_only"]
    assert c["denominator_violations"]["count"] == 0
    assert c["false_positive_satisfaction"]["count"] == 0
    assert c["cross_requirement_propagation"]["false_positive"] is False
    assert b["cross_requirement_propagation"]["false_positive"] is True
    assert b["denominator_violations"]["count"] > 0
    assert a["dropped_decidable_requirements"]["count"] > c["dropped_decidable_requirements"]["count"]


def test_or_contract_never_counts_one_requirement_twice(report):
    for strategy, r in report["or_contract"].items():
        assert r["overcount"]["count"] == 0, strategy


# ---------------------------------------------------------------------------
# Real-text track: aggregate-only output
# ---------------------------------------------------------------------------

_ALLOWED_REAL_KEYS = re.compile(r"^(?:available|rows|rows_located_verbatim|per_dataset|totals|interpretation|"
                                r"m11d|m11f|m11g9|R[1-6]_[a-z_]+|proposals|g1[12]_kept|posthoc_[a-z0-9_]+|"
                                r"row_text_contains_required_language|g12_kept_and_row_text_contains_required_language|"
                                r"preservation_generators|note)$")


def _walk(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def test_real_text_output_is_aggregate_only():
    path = M11G13 / "real_text_track_aggregates.json"
    if not path.exists():
        assert rtt.available() is False
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in _walk(data):
        assert _ALLOWED_REAL_KEYS.match(key), key
    for gen in data["totals"].values():
        assert all(isinstance(v, int) for v in gen.values())


# ---------------------------------------------------------------------------
# Portability and isolation
# ---------------------------------------------------------------------------


def test_g13_freeze_records_lf_normalized_hash():
    freeze = json.loads((M11G13 / "controls_hash_freeze.json").read_text(encoding="utf-8"))
    assert "sha256_lf_normalized" in freeze


def test_no_production_import_of_g13():
    offenders = [str(p) for p in (REPO_ROOT / "src" / "gitscore").rglob("*.py")
                 if "m11g13" in p.read_text(encoding="utf-8").lower()]
    assert offenders == []


def test_no_network_or_llm_usage():
    for rel in ("scripts/evaluation_lib/m11g13_build_controls.py", "scripts/evaluation_lib/m11g13_or_contract.py",
                "scripts/evaluation_lib/m11g13_real_text_track.py", "scripts/evaluation_lib/m11g13_gold_portability.py",
                "scripts/evaluate_m11g13_generalization.py"):
        src = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for forbidden in ("openai", "anthropic", "import requests", "httpx", "urllib.request", "import socket"):
            assert forbidden not in src, (rel, forbidden)


def test_g10_g11_g12_and_production_unchanged():
    paths = ["src", "scripts/evaluation_lib/m11g10_competency_concept_model.py",
             "scripts/evaluation_lib/m11g11_structured_extraction_feasibility.py",
             "scripts/evaluation_lib/m11g12_validator_hardening.py", "evaluation/m11g12"]
    proc = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", *paths], cwd=REPO_ROOT)
    assert proc.returncode == 0
