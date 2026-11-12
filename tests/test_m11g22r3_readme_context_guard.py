"""Milestone 11-G22-R3 -- README context guard validation (RESEARCH tests; readme:v5 NOT implemented).

G22-R3 changes no production code and no registry data. These tests pin:
  * the fresh VAL-1 / VAL-2 sets (separate author, frozen before any run; G14 portable hashes; registered at the
    research commit, 21 -> 23);
  * the design timeline: D unchanged on VAL-1, then R3 designed and frozen with acceptance criteria BEFORE VAL-2 ran;
  * the measured outcome: precision criteria pass, recall criteria fail for D and R3 -> readme:v5 not implemented;
  * R3's scope (non-ambiguous aliases untouched) and its documented cue behaviour;
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
import m11g22r2_policies as p2  # noqa: E402
import m11g22r2_posthoc as ph  # noqa: E402
import m11g22r3_policies as p3  # noqa: E402
from gitscore.assessment import SCORING_VERSION  # noqa: E402
from gitscore.concepts.registry import CONCEPT_REGISTRY_VERSION  # noqa: E402
from gitscore.evidence.extraction import readme as readme_mod  # noqa: E402
from gitscore.evidence.extraction.readme import EXTRACTOR_VERSION, evidence_from_readme  # noqa: E402
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION  # noqa: E402
from gitscore.matching import MATCHER_VERSION  # noqa: E402

DATA = ROOT / "evaluation" / "m11g22r3"
LIVE = (JOB_DESCRIPTION_PARSER_VERSION, EXTRACTOR_VERSION, MATCHER_VERSION, SCORING_VERSION) == (
    "job_description_parser:v15", "readme:v4", "requirement_matcher:v1", "github_evidence_alignment:v2")
only_measured = pytest.mark.skipif(not LIVE, reason="documents the measured readme:v4 / v15 / v1 / v2 production")


@pytest.fixture(scope="module")
def report():
    return json.loads((DATA / "readme_guard_report.json").read_text(encoding="utf-8"))


def _extracted(policy, sentence: str, concept: str) -> bool:
    with p2.applied(policy):
        ev = evidence_from_readme("o", "r", f"# demo\n\n{sentence}\n", "README.md")
    return concept in {e.concept_id for e in ev}


# ---- freezes and provenance -------------------------------------------------------------------------
@pytest.mark.parametrize("split,sha,n", [
    ("val1", "575c57c1698160d949eb879b5e4161a90af72dcf6a8cd99ed98ba5d64fb9d0ae", 75),
    ("val2", "fadc95eb858c949620a50216ab83af443c43a1c7025e89e42c797d76a951c759", 51)])
def test_validation_sets_are_frozen_and_registered_with_their_original_hashes(split, sha, n):
    rec = json.loads((DATA / f"{split}_hash_freeze.json").read_text(encoding="utf-8"))
    assert rec["sha256"] == rec["sha256_lf_normalized"] == sha and rec["canonical_contract"] == gi.CONTRACT
    raw = (DATA / f"validation_controls_{split}.json").read_bytes()
    assert gi.sha256(gi.canonical_bytes(raw)) == sha
    doc = json.loads(raw)
    assert len(doc["controls"]) == n and "NOT human-independent" in doc["authorship_disclosure"]
    # Current state: registered at the authorized research commit with the ORIGINAL freeze-time hash (21 -> 23 entries).
    rel = f"evaluation/m11g22r3/validation_controls_{split}.json"
    res = gi.verify_frozen_file(rel, f"evaluation/m11g22r3/{split}_hash_freeze.json")
    assert res.historical_raw_sha256 == sha
    manifest = json.loads((ROOT / "evaluation/integrity/canonical_hash_manifest.json").read_text(encoding="utf-8"))
    entry = manifest["entries"][rel]
    assert (entry["freeze_record"], entry["historical_raw_sha256"], entry["canonical_sha256"],
            entry["historical_newline_form"], entry["canonical_length_bytes"]) == \
        (f"evaluation/m11g22r3/{split}_hash_freeze.json", sha, sha, "lf", rec["length_bytes"])
    assert entry["attested_from_commit"] == "staged-for-commit-on-parent-9552543b415c3faa19d0420b98b67141bf9cea09"
    # Historical state, pinned exactly: at the parent commit 9552543 the manifest had 21 entries, neither G22-R3 set was
    # registered, and every one of those 21 entries is still present field for field (registration is additive only).
    # Exact coverage of tracked freezes is enforced by test_m11g14_gold_integrity's inventory rule.
    import subprocess
    parent = json.loads(subprocess.run(
        ["git", "show", "9552543b415c3faa19d0420b98b67141bf9cea09:evaluation/integrity/canonical_hash_manifest.json"],
        cwd=ROOT, check=True, capture_output=True).stdout)
    assert len(parent["entries"]) == 21 and rel not in parent["entries"]
    assert all(manifest["entries"][k] == v for k, v in parent["entries"].items())
    assert len(manifest["entries"]) >= 23


def test_author_provenance_records_the_blind_brief_and_the_raw_files():
    prov = json.loads((DATA / "author_provenance.json").read_text(encoding="utf-8"))
    assert "NOT human-independent" in prov["author"]
    assert "NO Policy D rules" in prov["author_inputs"]
    assert "no label edited" in prov["pre_freeze_checks"]
    assert set(prov["raw_author_files_sha256"]) == {"val1", "val2"}
    assert prov["val2_status"].startswith("reserve")


def test_r3_design_was_frozen_after_the_val_sets_and_before_val2_ran():
    design = json.loads((DATA / "policy_design_freeze.json").read_text(encoding="utf-8"))
    for f, sha in design["files"].items():
        assert gi.sha256(gi.canonical_bytes((ROOT / f).read_bytes())) == sha, f
    val2 = json.loads((DATA / "val2_hash_freeze.json").read_text(encoding="utf-8"))
    assert design["val2_controls_sha256"] == val2["sha256"] and design["frozen_at_utc"] > val2["frozen_at_utc"]
    assert len(design["acceptance_criteria_on_val2_declared_before_run"]) == 8  # 7 criteria + the failure rule
    assert design["post_hoc_changes"] == []
    assert "scripts/evaluation_lib/m11g22r2_posthoc.py" not in design["files"]


def test_policy_d_was_evaluated_unchanged():
    g22r2 = json.loads((ROOT / "evaluation/m11g22r2/policy_design_freeze.json").read_text(encoding="utf-8"))
    rel = "scripts/evaluation_lib/m11g22r2_policies.py"
    assert gi.sha256(gi.canonical_bytes((ROOT / rel).read_bytes())) == g22r2["files"][rel]


# ---- measured results and the decision ----------------------------------------------------------------
def test_policy_d_on_fresh_val1(report):
    a, d = (report["val1"][n]["aggregate"] for n in ("A_current_readme_v4", "D_hybrid_use_frames"))
    assert (a["false_supported"], d["false_supported"]) == (35, 9)
    assert d["false_supported_by_probe_class"].get("ordinary", 0) == 0
    assert (a["use_claims_retained"], d["use_claims_retained"]) == ([36, 36], [26, 36])
    assert d["corroborated_supported"] == [10, 10]
    assert report["val1"]["R3_context_guard"]["role"].startswith("DESIGN SET")


def test_held_out_val2_and_the_frozen_acceptance_criteria(report):
    agg = {n: v["aggregate"] for n, v in report["val2"].items()}
    assert [agg[n]["false_supported"] for n in ("A_current_readme_v4", "D_hybrid_use_frames", "R3_context_guard")] == [24, 7, 8]
    assert agg["R3_context_guard"]["use_claims_retained"] == [18, 23]
    assert agg["R3_context_guard"]["corroborated_supported"] == [6, 6]
    for key in ("R3_on_val2", "D_on_val2", "D_on_val1"):
        checks = report["acceptance"][key]["checks"]
        failed = sorted(c for c, v in checks.items() if not v[2])
        assert failed == ["4_genuine_use_items", "5_requirement_recall"], key
        assert report["acceptance"][key]["passed"] is False
    for n in ("D_hybrid_use_frames", "R3_context_guard"):
        assert report["val2"][n]["new_false_supported_vs_readme_v4"] == []
        assert report["val2"][n]["non_ambiguous_items_changed"] == 0


def test_readme_v5_was_not_implemented(report):
    assert report["decision"]["readme_v5_implemented"] is False
    assert (EXTRACTOR_VERSION, JOB_DESCRIPTION_PARSER_VERSION, MATCHER_VERSION, SCORING_VERSION,
            CONCEPT_REGISTRY_VERSION) == ("readme:v4", "job_description_parser:v15", "requirement_matcher:v1",
                                          "github_evidence_alignment:v2", 4)
    for py in (ROOT / "src").rglob("*.py"):
        assert "m11g22r3" not in py.read_text(encoding="utf-8"), py


def test_named_phrases_are_reported_as_measured(report):
    rows = {r["phrase"]: r for r in report["named_phrases"]}
    assert len(rows) == 8
    assert rows["python plotting helper"]["outcome"]["R3_context_guard"] == "missed"
    assert rows["store in Rust"]["outcome"]["R3_context_guard"] == "missed"
    assert rows["API design borrowed from Express"]["outcome"]["R3_context_guard"] == "false_supported"
    for phrase in ("free of rust", "local and express trains"):
        assert rows[phrase]["outcome"]["A_current_readme_v4"] == "false_supported"
        assert rows[phrase]["outcome"]["R3_context_guard"] == "true_not_supported"


# ---- R3 adapter behaviour ------------------------------------------------------------------------------
def test_r3_never_touches_non_ambiguous_aliases():
    sentence = "A small view layer inspired by FastAPI."
    assert _extracted(p2.A, sentence, "framework.fastapi")
    assert not _extracted(p2.D, sentence, "framework.fastapi")  # D applied its non-use frames to every alias
    assert _extracted(p3.R3, sentence, "framework.fastapi")     # R3: readme:v4 behaviour for non-ambiguous aliases


@pytest.mark.parametrize("sentence,concept,d,r3", [
    ("A Rust library for parsing logs.", "language.rust", False, True),        # software head noun
    ("Per-route rate limits for Flask apps.", "framework.flask", False, True),  # plural collocate head noun
    ("Keeps tools free of rust.", "language.rust", False, False),              # design-time trap (plural window withdrawn)
    ("Timetables for local and express trains.", "framework.express", False, False),
    ("Like the Rust compiler, it explains errors.", "language.rust", False, True),  # documented VAL-2 head-noun trap
    ("Ships a small python plotting helper.", "language.python", False, False),     # unresolved genuine use
])
def test_r3_cue_behaviour_is_as_documented(sentence, concept, d, r3):
    assert _extracted(p2.A, sentence, concept)
    assert _extracted(p2.D, sentence, concept) is d
    assert _extracted(p3.R3, sentence, concept) is r3


def test_every_adapter_restores_the_production_extractor():
    before = readme_mod.is_non_implementation_mention
    for p in (p2.A, p2.D, ph.D2, p3.R3):
        _extracted(p, "Built with React.", "framework.react")
    assert readme_mod.is_non_implementation_mention is before


def test_capability_contract_and_job_parsing_are_unaffected(report):
    cap = report["capability_contract"]
    assert all(v["valid_context_not_extracted"] == [] for v in cap.values())
    assert len({json.dumps(v["capability"], sort_keys=True) for v in cap.values()}) == 1
    for name, v in report["invariants"].items():
        assert v == {"capability_identical_for_all_concepts": True, "job_parsing_identical_on_all_corpora": True}, name


def test_simulated_8c_impact_is_identical_for_d_and_r3(report):
    pol = report["historical_8c_simulated"]["policies"]
    for n in ("D_hybrid_use_frames", "R3_context_guard"):
        assert pol[n]["removed_reviewed_reference"] == 5 and pol[n]["removed_reviewed_use"] == 1
        assert pol[n]["removed_unreviewed"] == 0 and pol[n]["became_undefined"] == []
        assert pol[n]["score_changes"] == {"8c_v1:torvalds/systems_cpp_01": [[2, 3, 67], [1, 3, 33]],
                                           "8c_v1_1:torvalds/systems_cpp_01": [[2, 3, 67], [1, 3, 33]]}


# ---- reproducibility / publication safety ---------------------------------------------------------------
@only_measured
def test_public_report_is_reproducible():
    import evaluate_m11g22r3_readme_guard as runner
    committed = gi.canonical_bytes((DATA / "readme_guard_report.json").read_bytes())
    assert gi.canonical_bytes(runner.encode(runner.build_report())) == committed


def test_private_aggregates_are_integer_counts_only_and_unchanged():
    agg = json.loads((DATA / "private_readme_guard_aggregates.json").read_text(encoding="utf-8"))
    assert set(agg["note"].split()) >= {"integer", "counts", "only"}
    for name, per in agg.items():
        if name == "note":
            continue
        for corpus, v in per.items():
            assert all(isinstance(x, int) and not isinstance(x, bool) for x in v.values()), (name, corpus)
            assert v["postings_changed"] == 0, (name, corpus)
