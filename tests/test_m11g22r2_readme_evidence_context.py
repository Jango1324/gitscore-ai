"""Milestone 11-G22-R2 -- README evidence context and confidence (RESEARCH tests).

G22-R2 changes no production code and no registry data. These tests pin:
  * the frozen DEV/EVAL controls (G14 portable hashes; registered at the research commit, 19 -> 21) and the
    policy-design freeze;
  * the measured readme:v4 behaviour on the new controls and on the frozen 8c fixtures;
  * the research adapters' fidelity (A == production; patches restored; capability and job parsing untouched);
  * the documented limits (difficult cases, the post-hoc D2 caveat);
  * reproducibility of the public report and the counts-only private aggregates.
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
import m11g22r2_posthoc as ph  # noqa: E402
from gitscore.assessment import SCORING_VERSION  # noqa: E402
from gitscore.concepts.registry import CONCEPT_REGISTRY_VERSION  # noqa: E402
from gitscore.evidence.extraction import readme as readme_mod  # noqa: E402
from gitscore.evidence.extraction.readme import EXTRACTOR_VERSION  # noqa: E402
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION  # noqa: E402
from gitscore.matching import MATCHER_VERSION  # noqa: E402

DATA = ROOT / "evaluation" / "m11g22r2"
LIVE = (JOB_DESCRIPTION_PARSER_VERSION, EXTRACTOR_VERSION, MATCHER_VERSION, SCORING_VERSION) == (
    "job_description_parser:v15", "readme:v4", "requirement_matcher:v1", "github_evidence_alignment:v2")
only_measured = pytest.mark.skipif(not LIVE, reason="documents the measured readme:v4 / v15 / v1 / v2 production")


@pytest.fixture(scope="module")
def report():
    return json.loads((DATA / "readme_context_report.json").read_text(encoding="utf-8"))


# ---- freezes ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("split,sha,n", [
    ("dev", "18c21a505a472182b2d3fd5bc23d29957a1806834108ed58e7aef19d7307b12b", 44),
    ("eval", "3a59672a55745927ab945e671f9b867854bb81f08c418271e9669136893bfa0e", 40)])
def test_controls_are_frozen_and_registered_with_their_original_hashes(split, sha, n):
    rec = json.loads((DATA / f"{split}_hash_freeze.json").read_text(encoding="utf-8"))
    assert rec["sha256"] == rec["sha256_lf_normalized"] == sha and rec["canonical_contract"] == gi.CONTRACT
    raw = (DATA / f"readme_context_controls_{split}.json").read_bytes()
    assert gi.sha256(gi.canonical_bytes(raw)) == sha
    doc = json.loads(raw)
    assert len(doc["controls"]) == n and "NOT an independent validation set" in doc["authorship_disclosure"]
    # registered at the authorized research commit with the ORIGINAL freeze-time hash (19 -> 21 entries)
    rel = f"evaluation/m11g22r2/readme_context_controls_{split}.json"
    res = gi.verify_frozen_file(rel, f"evaluation/m11g22r2/{split}_hash_freeze.json")
    assert res.historical_raw_sha256 == sha
    manifest = json.loads((ROOT / "evaluation/integrity/canonical_hash_manifest.json").read_text(encoding="utf-8"))
    entry = manifest["entries"][rel]
    assert (entry["freeze_record"], entry["historical_raw_sha256"], entry["canonical_sha256"],
            entry["historical_newline_form"], entry["canonical_length_bytes"]) == \
        (f"evaluation/m11g22r2/{split}_hash_freeze.json", sha, sha, "lf", rec["length_bytes"])
    assert entry["attested_from_commit"] == "staged-for-commit-on-parent-13f79fe04ec7d962e3e94ddd0a1003b8dab999f8"
    # Additive only: the 19 entries present at the parent commit 13f79fe are unchanged, field for field. Exact coverage
    # of the tracked freezes is enforced by test_m11g14_gold_integrity's inventory rule, not by a hard-coded count here.
    import subprocess
    parent = json.loads(subprocess.run(
        ["git", "show", "13f79fe04ec7d962e3e94ddd0a1003b8dab999f8:evaluation/integrity/canonical_hash_manifest.json"],
        cwd=ROOT, check=True, capture_output=True).stdout)
    assert len(parent["entries"]) == 19 and rel not in parent["entries"]
    assert all(manifest["entries"][k] == v for k, v in parent["entries"].items())
    assert len(manifest["entries"]) >= 21


def test_policy_design_freeze_matches_and_excludes_the_post_hoc_variant():
    design = json.loads((DATA / "policy_design_freeze.json").read_text(encoding="utf-8"))
    for f, sha in design["files"].items():
        assert gi.sha256(gi.canonical_bytes((ROOT / f).read_bytes())) == sha, f
    assert "scripts/evaluation_lib/m11g22r2_posthoc.py" not in design["files"]
    assert design["post_hoc_changes"] == []
    assert design["frozen_at_utc"] > json.loads((DATA / "eval_hash_freeze.json").read_text(encoding="utf-8"))["frozen_at_utc"]


def test_controls_cover_the_required_cases():
    controls = h.load_controls("dev") + h.load_controls("eval")
    classes = {k for c in controls for k in c["concepts"].values()}
    assert classes == {"ordinary", "reference", "use", "historical", "future", "negated", "ambiguous"}
    fams = {c["family"] for c in controls}
    assert {"corroborated_manifest", "corroborated_language", "corroborated_docker", "readme_only_use",
            "multi_repo_use", "conflicting", "quoted_ordinary"} <= fams
    assert {c["pair"] for c in controls if c["pair"]} >= {"rust-free-of", "express-and", "java-cap", "ruby"}


# ---- measured production behaviour --------------------------------------------------------------------
@only_measured
@pytest.mark.parametrize("cid", ["m11g22r2-d02", "m11g22r2-d03", "m11g22r2-d04", "m11g22r2-d05", "m11g22r2-d24",
                                 "m11g22r2-d25"])
def test_readme_v4_turns_ordinary_reference_and_future_text_into_false_supported(cid):
    c = next(x for x in h.load_controls("dev") if x["id"] == cid)
    r = h.run_control(c, p2.A)
    assert r["outcome"] == "false_supported" and r["probe_evidence_types"] == ["readme"] and r["score"] == 100


@only_measured
def test_readme_v4_labels_every_readme_item_moderate(report):
    assert report["readme_semantics_8c"]["confidence_levels"] == ["MODERATE"]
    assert report["readme_semantics_8c"]["readme_items"] == 126


def test_real_8c_bindings_list_was_false_evidence_and_d_removes_it(report):
    d = report["historical_8c"]["policies"]["D_hybrid_use_frames"]
    removed = {(c, r, k): rev for c, r, k, rev, _ in d["readme_items_removed"]}
    for lang in ("language.java", "language.ruby", "language.rust", "language.swift", "language.python"):
        assert removed[("torvalds", "libgit2", lang)].startswith("reference")
    assert d["removed_reviewed_use"] == 1 and d["removed_unreviewed"] == 0
    assert list(d["score_changes"]) == ["8c_v1:torvalds/systems_cpp_01", "8c_v1_1:torvalds/systems_cpp_01"]
    assert d["became_undefined"] == []


# ---- adapters -------------------------------------------------------------------------------------------
def test_policy_a_is_production_and_every_policy_restores_the_extractor():
    before = readme_mod.is_non_implementation_mention
    c = h.load_controls("dev")[0]
    assert h.run_control(c, p2.A) == h.run_control(c)
    for p in (*p2.POLICIES, *ph.POSTHOC):
        h.run_control(c, p)
    assert readme_mod.is_non_implementation_mention is before


def test_readme_policies_never_touch_capability_or_job_parsing(report):
    for name, v in report["invariants"].items():
        assert v == {"capability_identical_for_all_concepts": True, "job_parsing_identical_on_all_corpora": True}, name


def test_existing_extractor_and_pipeline_tests_only_fail_where_g22r_pins_readme_v4(report):
    t = report["existing_tests_under_policies"]
    assert t["A_current_readme_v4"]["failed"] == []
    for name, v in t.items():
        if name != "files":
            assert all("test_m11g22r_ambiguous_alias_evidence.py" in f for f in v["failed"]), name


# ---- findings and limits -------------------------------------------------------------------------------
def test_policy_comparison_headline(report):
    a = {s: {p: v["aggregate"] for p, v in report["controls"][s].items()} for s in ("dev", "eval")}
    assert (a["dev"]["A_current_readme_v4"]["false_supported"], a["eval"]["A_current_readme_v4"]["false_supported"]) == (21, 18)
    assert (a["dev"]["D_hybrid_use_frames"]["false_supported"], a["eval"]["D_hybrid_use_frames"]["false_supported"]) == (0, 1)
    assert a["eval"]["D_hybrid_use_frames"]["use_claims_retained"] == [16, 19]
    for p in ("E_corroboration_interpretation", "F_conservative_fallback"):
        assert a["eval"][p]["false_supported"] == 0 and a["eval"][p]["use_claims_retained"] == [5, 19]
    for s in ("dev", "eval"):
        for p, v in a[s].items():
            assert v["corroborated_supported"] == [4, 4], (s, p)


def test_post_hoc_d2_is_labelled_and_its_traps_are_recorded(report):
    assert report["post_hoc_policies"]["names"] == ["D2_posthoc_d_plus_lead_ins"]
    assert "NOT validation" in report["post_hoc_policies"]["caveat"]
    cases = {c["case"]: c for c in report["difficult_cases"]}
    assert cases["in Java, ordinary (D2 TRAP)"]["extracted"]["D2_posthoc_d_plus_lead_ins"] is True
    assert cases["capitalised Java + app collocate (TRAP)"]["extracted"]["D_hybrid_use_frames"] is True
    assert cases["borrowed from Express (reference)"]["extracted"]["D_hybrid_use_frames"] is True


def test_g21_n10_is_a_job_side_case_readme_policies_cannot_reach(report):
    n10 = report["g21_n10"]
    assert n10["job_side_rows"]["BASE"] == [[["framework.react"], "preferred"]]
    assert n10["job_side_rows"]["B_ambiguous_alias_cue"] == []
    assert n10["readme_policies_affect_it"] is False


# ---- reproducibility / publication safety ---------------------------------------------------------------
@only_measured
def test_public_report_is_reproducible_except_the_existing_test_runs(report):
    import evaluate_m11g22r2_readme_context as runner
    committed = json.loads(gi.canonical_bytes((DATA / "readme_context_report.json").read_bytes()))
    live = json.loads(runner.encode(runner.build_report(run_tests=False)))
    committed.pop("existing_tests_under_policies")
    live.pop("existing_tests_under_policies")
    assert live == committed


def test_private_aggregates_are_integer_counts_only_and_unchanged():
    agg = json.loads((DATA / "private_readme_context_aggregates.json").read_text(encoding="utf-8"))
    assert set(agg["note"].split()) >= {"integer", "counts", "only"}
    for name, per in agg.items():
        if name == "note":
            continue
        for corpus, v in per.items():
            assert all(isinstance(x, int) and not isinstance(x, bool) for x in v.values()), (name, corpus)
            assert v["postings_changed"] == 0, (name, corpus)


def test_production_is_unchanged_and_never_imports_the_research_adapters():
    assert JOB_DESCRIPTION_PARSER_VERSION == "job_description_parser:v15"
    assert SCORING_VERSION == "github_evidence_alignment:v2"
    assert MATCHER_VERSION == "requirement_matcher:v1"
    assert EXTRACTOR_VERSION == "readme:v4"
    assert CONCEPT_REGISTRY_VERSION == 4
    for py in (ROOT / "src").rglob("*.py"):
        assert "m11g22r2" not in py.read_text(encoding="utf-8"), py
