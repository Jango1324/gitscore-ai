"""Milestone 11-G22-R4 -- high-recall (inverse) README evidence guard research (RESEARCH tests; readme:v5 NOT
implemented).

G22-R4 changes no production code and no registry data. These tests pin:
  * the R4 DEV and fresh validation freezes (G14 portable hashes; registered at the authorized research commit with
    their original freeze-time hashes, 23 -> 25, additively over the G22-R3 commit 8241a24);
  * the chronology: DEV frozen -> policy design frozen -> fresh set frozen, and the frozen policy files unchanged;
  * the measured held-out outcome: the chosen P4 keeps all genuine README use but misses the frozen >= 50% false
    SUPPORTED reduction gate (42 -> 24), so it is not recommended;
  * P4's documented behaviour: default-accept, bounded rejections with reasons, near-neighbour pairs, fall-through
    to a later genuine occurrence, non-ambiguous aliases untouched, every README-safe alias still extractable;
  * the counts-only private aggregates.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "src", ROOT / "scripts", ROOT / "scripts" / "evaluation_lib"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import gold_integrity as gi  # noqa: E402
import m11g22r2_harness as h  # noqa: E402
import m11g22r2_policies as p2  # noqa: E402
import m11g22r4_policies as p4  # noqa: E402
from gitscore.assessment import SCORING_VERSION  # noqa: E402
from gitscore.concepts.matching import alias_pattern  # noqa: E402
from gitscore.concepts.registry import CONCEPT_REGISTRY_VERSION, default_registry  # noqa: E402
from gitscore.evidence.extraction.readme import EXTRACTOR_VERSION, evidence_from_readme  # noqa: E402
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION  # noqa: E402
from gitscore.matching import MATCHER_VERSION  # noqa: E402

DATA = ROOT / "evaluation" / "m11g22r4"
DEV_SHA = "8e1034770d543e25a843700cfee11294d1c45058065aa2c348cab6955374cd3e"
FRESH_SHA = "8d003c6ef6f873a43d6618a7775d575b780d1d5eccfcf3b6c99966667d3b92ed"
LIVE = (JOB_DESCRIPTION_PARSER_VERSION, EXTRACTOR_VERSION, MATCHER_VERSION, SCORING_VERSION) == (
    "job_description_parser:v15", "readme:v4", "requirement_matcher:v1", "github_evidence_alignment:v2")
only_measured = pytest.mark.skipif(not LIVE, reason="documents the measured readme:v4 / v15 / v1 / v2 production")


@pytest.fixture(scope="module")
def report():
    return json.loads((DATA / "high_recall_guard_report.json").read_text(encoding="utf-8"))


def _extracted(policy, text: str, concept: str) -> bool:
    with p2.applied(policy):
        ev = evidence_from_readme("o", "r", text if text.startswith("#") else f"# demo\n\n{text}\n", "README.md")
    return concept in {e.concept_id for e in ev}


# ---- freezes, provenance and chronology ---------------------------------------------------------------
@pytest.mark.parametrize("data,record,sha,n", [("dev_controls.json", "dev_hash_freeze.json", DEV_SHA, 60),
                                               ("fresh_validation_controls.json", "fresh_hash_freeze.json", FRESH_SHA,
                                                96)])
def test_r4_sets_are_frozen_and_registered_with_their_original_hashes(data, record, sha, n):
    rec = json.loads((DATA / record).read_text(encoding="utf-8"))
    assert rec["sha256"] == rec["sha256_lf_normalized"] == sha and rec["canonical_contract"] == gi.CONTRACT
    raw = (DATA / data).read_bytes()
    assert gi.sha256(gi.canonical_bytes(raw)) == sha
    assert len(json.loads(raw)["controls"]) == n
    # the freeze record keeps its freeze-time wording; it is never rewritten on registration
    assert "NOT registered" in rec["note"]
    # Current state: registered at the authorized research commit with the ORIGINAL freeze-time hash (23 -> 25).
    rel = f"evaluation/m11g22r4/{data}"
    res = gi.verify_frozen_file(rel, f"evaluation/m11g22r4/{record}")
    assert res.historical_raw_sha256 == sha
    entry = json.loads(gi.DEFAULT_MANIFEST.read_text(encoding="utf-8"))["entries"][rel]
    assert (entry["freeze_record"], entry["historical_raw_sha256"], entry["canonical_sha256"],
            entry["historical_newline_form"], entry["canonical_length_bytes"]) == \
        (f"evaluation/m11g22r4/{record}", sha, sha, "lf", rec["length_bytes"])
    assert entry["attested_from_commit"] == "staged-for-commit-on-parent-8241a24b9e0d07ebd33835bd1a20d3cddab6e429"


def test_manifest_registration_is_additive_over_the_g22r3_commit():
    """Pinned historical state: at the G22-R3 commit 8241a24 the manifest had 23 entries and neither R4 set; every
    one of those 23 entries is still present field for field, all current entries verify, and the only additions are
    the two R4 sets. Exact coverage of tracked freezes is enforced by test_m11g14_gold_integrity's inventory rule."""
    import subprocess
    parent = json.loads(subprocess.run(
        ["git", "show", "8241a24b9e0d07ebd33835bd1a20d3cddab6e429:evaluation/integrity/canonical_hash_manifest.json"],
        cwd=ROOT, check=True, capture_output=True).stdout)
    r4 = {"evaluation/m11g22r4/dev_controls.json", "evaluation/m11g22r4/fresh_validation_controls.json"}
    assert len(parent["entries"]) == 23 and not (r4 & set(parent["entries"]))
    manifest = json.loads(gi.DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    assert all(manifest["entries"][k] == v for k, v in parent["entries"].items())
    assert {k: v for k, v in manifest.items() if k != "entries"} == {k: v for k, v in parent.items() if k != "entries"}
    assert r4 <= set(manifest["entries"]) and len(manifest["entries"]) >= 25
    for frozen, e in manifest["entries"].items():
        gi.verify_frozen_file(frozen, e["freeze_record"])


def test_design_freeze_chronology_and_frozen_files_unchanged():
    design = json.loads((DATA / "policy_design_freeze.json").read_text(encoding="utf-8"))
    for f, sha in design["files"].items():
        assert gi.sha256(gi.canonical_bytes((ROOT / f).read_bytes())) == sha, f
    dev = json.loads((DATA / "dev_hash_freeze.json").read_text(encoding="utf-8"))["frozen_at_utc"]
    fresh = json.loads((DATA / "fresh_hash_freeze.json").read_text(encoding="utf-8"))["frozen_at_utc"]
    assert dev < design["frozen_at_utc"] < fresh
    assert design["chosen_candidate"] == p4.P4.name and design["post_hoc_changes"] == []
    prov = json.loads((DATA / "fresh_author_provenance.json").read_text(encoding="utf-8"))
    assert prov["raw_author_files_sha256"] == design["fresh_raw_author_files_sha256_before_freeze"]
    assert "NOT human-independent" in prov["author"] and "leakage_disclosure" in prov
    assert prov["pre_freeze_checks"]["counts"] == {"unlabelled_mentions": 0, "labels_without_mention": 0, "cases": 96}
    # the R2 / R3 policy and harness files the R4 adapters reuse are byte-identical to their own historical freeze
    r3 = json.loads((ROOT / "evaluation/m11g22r3/policy_design_freeze.json").read_text(encoding="utf-8"))["files"]
    for f in set(r3) & set(design["files"]):
        assert r3[f] == design["files"][f], f


def test_research_adapters_are_not_imported_by_production():
    for path in (ROOT / "src").rglob("*.py"):
        assert "m11g22r4" not in path.read_text(encoding="utf-8"), path


@only_measured
def test_production_versions_unchanged():
    assert (JOB_DESCRIPTION_PARSER_VERSION, SCORING_VERSION, MATCHER_VERSION, EXTRACTOR_VERSION,
            CONCEPT_REGISTRY_VERSION) == ("job_description_parser:v15", "github_evidence_alignment:v2",
                                          "requirement_matcher:v1", "readme:v4", 4)


# ---- the held-out decision --------------------------------------------------------------------------------
@only_measured
def test_fresh_gate_outcome_is_recorded_as_measured(report):
    acc = report["acceptance"]
    assert acc["policy"] == "P4_hybrid_overrides" and acc["passed"] is False
    checks = {k: v[2] for k, v in acc["checks"].items()}
    assert checks == {"G1_genuine_readme_use_retention": True, "G2_true_supported_retention": True,
                      "G3_false_supported_reduction": False, "G4_no_new_false_supported": True,
                      "G5_corroborated": True, "G6_non_ambiguous": True, "G7_g19_capability": True,
                      "G8_no_job_side_regression": True}
    assert acc["checks"]["G3_false_supported_reduction"][:2] == [24, 42]
    a = report["fresh"]["results"]
    assert a["P4_hybrid_overrides"]["aggregate"]["use_claims_retained"] == [88, 88]
    assert (a["D_hybrid_use_frames"]["aggregate"]["false_supported"],
            a["R3_context_guard"]["aggregate"]["false_supported"]) == (14, 15)


@only_measured
def test_fresh_primary_result_reproduces_for_the_frozen_policy(report):
    """A deterministic re-run of the SAME frozen policy (not a new assessment) reproduces the recorded numbers."""
    ctrl = json.loads((DATA / "fresh_validation_controls.json").read_text(encoding="utf-8"))["controls"]
    for policy in (p2.A, p4.P4):
        agg = h.aggregate([h.run_control(c, policy) for c in ctrl], ctrl)
        rec = report["fresh"]["results"][policy.name]["aggregate"]
        for k in ("false_supported", "use_claims_retained", "true_supported", "corroborated_supported"):
            assert agg[k] == rec[k], (policy.name, k)


# ---- P4 behaviour ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("text,concept,kept", [
    ("Express train simulator built in Rust.", "language.rust", True),
    ("Express train simulator built in Rust.", "framework.express", False),
    ("Rust removal tool written in Python.", "language.python", True),
    ("Rust removal tool written in Python.", "language.rust", False),
    ("A Ruby gemstone catalog built in Ruby.", "language.ruby", True),
    ("A ruby gemstone photographed under four lights.", "language.ruby", False),
    ("Pure Python TOML parser.", "language.python", True),
    ("The keeper weighs a ball python every week.", "language.python", False),
    ("One-line Swift API for the keychain.", "language.swift", True),
    ("A swift response to every bug report.", "language.swift", False),
    ("React-based UI for monitoring vans.", "framework.react", True),
    ("Lets dispatchers react quickly when a van breaks down.", "framework.react", False),
    ("Flask application that tracks lab glassware.", "framework.flask", True),
    ("Shake the flask before measuring.", "framework.flask", False),
    ("Torch training framework for small vision models.", "ml.framework.pytorch", True),
    ("Remember to carry a torch on night shifts.", "ml.framework.pytorch", False),
    ("Bindings for Rust can be generated with bindgen.", "language.rust", False),
    ("The Rust bindings in `bindings/rust` are maintained here.", "language.rust", True),
    ("A Java and Kotlin Android app.", "language.java", True),
    ("Like the Rust compiler, it explains every error.", "language.rust", False),
    ("Built with modern tools like React and Vite.", "framework.react", True),
])
def test_p4_near_neighbours(text, concept, kept):
    assert _extracted(p4.P4, text, concept) is kept
    assert _extracted(p2.A, text, concept) is True  # readme:v4 extracts every one of them


def test_rejection_falls_through_to_a_later_genuine_occurrence():
    text = "# pager\n\nHelps on-call teams react to alerts early. The dashboard is a React app.\n"
    assert _extracted(p4.P4, text, "framework.react")
    with p2.applied(p4.P4):
        (ev,) = [e for e in evidence_from_readme("o", "r", text, "README.md") if e.concept_id == "framework.react"]
    assert "React app" in ev.raw_observation


def test_every_rejection_carries_a_rule_reason():
    text = "# x\n\nNo React here. Originally a Flask app. Free of rust. Bindings for Ruby are planned.\n"
    reasons = [p4.explain(text, o.start, o.end, 4) for o in p4.occurrences(text)]
    assert len(reasons) == 4 and all(r and r.split()[0] in {"P1", "P2", "P3"} for r in reasons)


def test_non_ambiguous_aliases_are_never_rejected():
    reg = default_registry()
    for c in reg.all_concepts():
        for alias in c.readme_safe_aliases():
            if alias in p4.AMBIGUOUS:
                continue
            for frame in ("No {} needed.", "Inspired by {}.", "We plan to add {} later.", "a {}, and more"):
                text = "# x\n\n" + frame.format(alias) + "\n"
                for m in alias_pattern(alias).finditer(text):
                    assert p4.explain(text, m.start(), m.end(), 4) is None, (alias, frame)


@pytest.mark.parametrize("policy", p4.CANDIDATES, ids=lambda p: p.name)
def test_every_readme_safe_alias_still_extractable(policy):
    reg = default_registry()
    for c in reg.all_concepts():
        for alias in c.readme_safe_aliases():
            assert _extracted(policy, f"This project is built with {alias}.", c.concept_id), (c.concept_id, alias)


def test_paragraph_sentence_model_joins_soft_wraps_only():
    text = "If you write in a language\nlike .NET, Node.js, or Ruby, then\nbind.\n\n- item Rust\n"
    ruby = next(o for o in p4.occurrences(text) if o.alias == "ruby")
    assert p4.explain(text, ruby.start, ruby.end, 4) == "P3 'like <alias>' comparison"
    rust = next(o for o in p4.occurrences(text) if o.alias == "rust")
    assert p4._occurrence(text, rust.start, rust.end)[0] == "- item Rust"


# ---- privacy ----------------------------------------------------------------------------------------------
def test_private_aggregates_are_integer_counts_only():
    agg = json.loads((DATA / "private_high_recall_guard_aggregates.json").read_text(encoding="utf-8"))

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k != "note":
                    yield from walk(v)
        else:
            yield o
    assert all(isinstance(v, int) for v in walk({k: v for k, v in agg.items() if k != "note"}))
    assert all(v["postings_changed"] == 0 for k, d in agg.items() if k != "note" for v in d.values())
