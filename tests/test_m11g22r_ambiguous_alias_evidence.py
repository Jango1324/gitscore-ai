"""Milestone 11-G22-R -- ambiguous alias and README evidence audit (RESEARCH tests).

G22-R changes no production code. These tests pin:
  * the frozen DEV/EVAL controls and the policy-design freeze (G14 portable hashes; registered in the
    manifest at the authorized research commit with their original freeze-time hashes);
  * the measured production behaviour (parser v15, README extractor readme:v4, matcher, scoring v2):
    ordinary-English README text becomes README evidence and a counted SUPPORTED requirement;
  * which alias logic is shared (job parser, README extractor, capability) and which is independent;
  * the research adapters' fidelity (BASE == production; patches always restored; capability untouched);
  * reproducibility of the committed public report and the counts-only private aggregates.
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
import m11g22r_harness as h  # noqa: E402
import m11g22r_policies as rpol  # noqa: E402
from gitscore.assessment import SCORING_VERSION  # noqa: E402
from gitscore.evidence.capability import EvidencePathway, concept_capability  # noqa: E402
from gitscore.evidence.extraction import readme as readme_mod  # noqa: E402
from gitscore.evidence.extraction.readme import EXTRACTOR_VERSION, evidence_from_readme  # noqa: E402
from gitscore.jobs.parsing import parser as parser_mod  # noqa: E402
from gitscore.jobs.parsing.concepts import find_concept_mentions  # noqa: E402
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION  # noqa: E402

DATA = ROOT / "evaluation" / "m11g22r"
LIVE = JOB_DESCRIPTION_PARSER_VERSION == "job_description_parser:v15" and EXTRACTOR_VERSION == "readme:v4"


def _repo_control(readme: str, languages: dict | None = None, files: dict | None = None, probe="framework.react",
                  mentioned=(), used=()):
    return {"id": "t", "family": "t", "cell": None, "alias": None, "job_text": None, "job_concepts": [],
            "repos": [{"name": "r", "readme": readme, "languages": languages or {}, "files": files or {}}],
            "mentioned": list(mentioned), "used": list(used), "probe": probe}


# ---- freezes ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("split,sha,n", [
    ("dev", "b7c42f5904f4191824083a5fa5175cdf5ec18ff16d5f871d77b04f3fc5bf2172", 40),
    ("eval", "15ae7d6951cafe3ce139e4266e5123c30459d104556237a41534f8c2f8999a81", 36)])
def test_controls_are_frozen_and_registered_with_their_original_hashes(split, sha, n):
    rec = json.loads((DATA / f"{split}_hash_freeze.json").read_text(encoding="utf-8"))
    assert rec["sha256"] == rec["sha256_lf_normalized"] == sha and rec["canonical_contract"] == gi.CONTRACT
    raw = (DATA / f"alias_evidence_controls_{split}.json").read_bytes()
    assert gi.sha256(gi.canonical_bytes(raw)) == sha
    doc = json.loads(raw)
    assert len(doc["controls"]) == n and "NOT an independent validation set" in doc["authorship_disclosure"]
    # registered at the authorized research commit with the ORIGINAL freeze-time hash (17 -> 19 entries)
    manifest = json.loads((ROOT / "evaluation/integrity/canonical_hash_manifest.json").read_text(encoding="utf-8"))
    entry = manifest["entries"][f"evaluation/m11g22r/alias_evidence_controls_{split}.json"]
    assert (entry["freeze_record"], entry["historical_raw_sha256"], entry["canonical_sha256"],
            entry["historical_newline_form"], entry["canonical_length_bytes"]) == \
        (f"evaluation/m11g22r/{split}_hash_freeze.json", sha, sha, "lf", rec["length_bytes"])
    # Later research commits may only ADD entries (M11-G22-R2: 19 -> 21), so the historical fact is pinned exactly:
    # the manifest at G22-R's commit had 19 entries, and every one of them is still present, field for field.
    import subprocess
    at_g22r = json.loads(subprocess.run(
        ["git", "show", "13f79fe04ec7d962e3e94ddd0a1003b8dab999f8:evaluation/integrity/canonical_hash_manifest.json"],
        cwd=ROOT, check=True, capture_output=True).stdout)
    rel = f"evaluation/m11g22r/alias_evidence_controls_{split}.json"
    assert len(at_g22r["entries"]) == 19 and at_g22r["entries"][rel] == entry
    assert all(manifest["entries"][k] == v for k, v in at_g22r["entries"].items())


def test_policy_design_freeze_matches_the_files_and_records_the_errata():
    design = json.loads((DATA / "policy_design_freeze.json").read_text(encoding="utf-8"))
    for f, sha in design["files"].items():
        assert gi.sha256(gi.canonical_bytes((ROOT / f).read_bytes())) == sha, f
    assert design["post_hoc_changes"] == []
    assert "m11g22r-d22" in design["label_errata"]


def test_controls_cover_every_paired_cell_and_family():
    controls = h.load_controls("dev") + h.load_controls("eval")
    assert {c["cell"] for c in controls if c["cell"]} == set(range(1, 11))
    assert {c["alias"] for c in controls} >= {"react", "express", "swift", "rust", "shell", "torch", "ruby", "flask",
                                              "pandas", "python", "java"}
    assert {"readme_ordinary", "readme_genuine", "readme_mention_no_use", "job_ordinary", "job_genuine",
            "paired"} <= {c["family"] for c in controls}


# ---- shared vs independent alias logic --------------------------------------------------------------
def test_job_parser_readme_extractor_and_capability_share_one_alias_table():
    text = "Helps maintainers react quickly to new issues."
    assert [m.concept_id for m in find_concept_mentions(text)] == ["framework.react"]
    assert [e.concept_id for e in evidence_from_readme("o", "r", text, "README.md")] == ["framework.react"]
    assert EvidencePathway.README_MENTION in concept_capability("framework.react").pathways


@pytest.mark.skipif(not LIVE, reason="documents parser v15 / readme:v4 production behaviour")
def test_structured_extractors_do_not_scan_prose():
    # language statistics and manifests resolve exact names; a README sentence never reaches them
    r = h.run_control(_repo_control("# x\n\nA tiny tool.\n", {"Swift": 9000}, probe="language.swift",
                                    used=["language.swift"]))
    assert [(e["type"], e["concept"]) for e in r["evidence"]] == [("repository_language", "language.swift")]
    r = h.run_control(_repo_control("# x\n\nA tiny tool.\n", {"Python": 9000}, {"requirements.txt": "flask==3.0\n"},
                                    probe="framework.flask", used=["framework.flask", "language.python"]))
    assert ("dependency", "framework.flask", "STRONG") in [(e["type"], e["concept"], e["confidence"]) for e in r["evidence"]]


# ---- measured production failures (version-gated to the measured production) ------------------------
@pytest.mark.skipif(not LIVE, reason="documents parser v15 / readme:v4 production behaviour")
@pytest.mark.parametrize("readme,concept", [
    ("A small bot that helps maintainers react quickly to new issues.", "framework.react"),
    ("Users can express their opinion about each release.", "framework.express"),
    ("A swift, dependency-free CSV parser.", "language.swift"),
    ("Removes rust stains from scanned photographs.", "language.rust"),
    ("We pass the torch to new maintainers every year.", "ml.framework.pytorch"),
    ("Feeding schedule tracker for a ball python.", "language.python"),
])
def test_ordinary_english_readme_text_becomes_supported_evidence(readme, concept):
    r = h.run_control(_repo_control(f"# x\n\n{readme}\n", {"Dart": 9000}, probe=concept))
    (ev,) = [e for e in r["evidence"] if e["type"] == "readme"]
    assert (ev["concept"], ev["confidence"], ev["extractor"]) == (concept, "MODERATE", "readme:v4")
    (row,) = r["rows"]
    assert (row["status"], row["counts"], r["score"]) == ("supported", True, 100)
    assert r["false_supported"] == [{"members": [concept], "cause": "false_readme_extraction"}]


@pytest.mark.skipif(not LIVE, reason="documents parser v15 / readme:v4 production behaviour")
def test_existing_attribution_filter_still_excludes_explicit_non_use():
    r = h.run_control(_repo_control("# x\n\nA Node router. It does not use Express.\n", {"JavaScript": 9000},
                                    probe="framework.express", mentioned=["framework.express"],
                                    used=["language.javascript"]))
    assert [e for e in r["evidence"] if e["type"] == "readme" and e["concept"] == "framework.express"] == []
    assert r["rows"][0]["status"] == "not_observed"


# ---- research adapters -------------------------------------------------------------------------------
def test_base_policy_is_production_and_every_policy_restores_production_functions():
    before = (readme_mod.is_non_implementation_mention, parser_mod.decide_qualification_intent,
              parser_mod.find_concept_mentions, parser_mod.classify_alternative_claim)
    for c in h.load_controls("dev")[:5]:
        assert h.run_control(c, rpol.BASE) == h.run_control(c)
    for p in rpol.POLICIES:
        h.run_control(h.load_controls("dev")[0], p)
    assert (readme_mod.is_non_implementation_mention, parser_mod.decide_qualification_intent,
            parser_mod.find_concept_mentions, parser_mod.classify_alternative_claim) == before


def test_occurrence_guards_never_change_capability_but_alias_table_changes_would():
    report = json.loads((DATA / "alias_evidence_report.json").read_text(encoding="utf-8"))
    cap = report["capability"]
    assert cap["occurrence_guards_leave_capability_unchanged"] is True
    w = cap["alias_table_whatif"]
    assert w["flask"]["capability_if_alias_marked_unsafe"] == ["not_assessable", []]
    assert w["pandas"]["capability_if_alias_marked_unsafe"] == ["not_assessable", []]
    assert w["react"]["job_parser_would_still_recognise_display_name"] is False


def test_policy_d_keeps_genuine_readme_and_job_recall_on_dev_and_eval():
    report = json.loads((DATA / "alias_evidence_report.json").read_text(encoding="utf-8"))
    for split in ("dev", "eval"):
        base = report["controls"][split]["BASE"]["aggregate"]
        d = report["controls"][split]["D_alias_metadata_split"]["aggregate"]
        assert d["readme_genuine_recall"] == base["readme_genuine_recall"]
        assert d["job_missed_concepts"] == base["job_missed_concepts"] == 0
        assert d["job_false_concepts"] == 0 < base["job_false_concepts"]
        assert d["false_supported"] < base["false_supported"]


def test_historical_frozen_8c_scores_are_unchanged_by_every_occurrence_guard():
    report = json.loads((DATA / "alias_evidence_report.json").read_text(encoding="utf-8"))
    hist = report["historical_evidence_8c"]["policies"]
    for name in ("A_job_generic_usage", "B_readme_generic_usage", "C_shared_generic_usage", "D_alias_metadata_split"):
        assert hist[name]["score_or_denominator_changed"] == {} and hist[name]["status_changed_pairs"] == [], name
    assert len(hist["R_readme_only_insufficient"]["score_or_denominator_changed"]) == 8  # study only: semantic change
    for name, v in report["existing_tests_under_policies"].items():
        if name != "files":
            assert v["failed"] == [] and v["summary"] == "337 passed", name


def test_g22q_equivalence_survives_every_policy():
    report = json.loads((DATA / "alias_evidence_report.json").read_text(encoding="utf-8"))
    for name, cases in report["g22q_equivalence_under_policies"].items():
        assert cases["G15-I1"] == [[["infra.kubernetes"], "infrastructure"]], name
        assert cases["G18-16"] == [[["language.go"], "language"]], name


# ---- reproducibility / publication safety ----------------------------------------------------------------
@pytest.mark.skipif(not LIVE, reason="the committed report measures parser v15 / readme:v4")
def test_public_report_is_reproducible_except_the_existing_test_runs():
    import evaluate_m11g22r_alias_evidence as runner
    committed = json.loads(gi.canonical_bytes((DATA / "alias_evidence_report.json").read_bytes()))
    live = json.loads(runner.encode(runner.build_report(run_tests=False)))
    committed.pop("existing_tests_under_policies")
    live.pop("existing_tests_under_policies")
    assert live == committed


def test_private_aggregates_are_integer_counts_only():
    agg = json.loads((DATA / "private_alias_aggregates.json").read_text(encoding="utf-8"))
    assert set(agg["note"].split()) >= {"integer", "counts", "only"}

    def walk(obj):
        if isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        else:
            assert isinstance(obj, int) and not isinstance(obj, bool), obj
    walk({k: v for k, v in agg.items() if k != "note"})


def test_production_is_unchanged_and_never_imports_the_research_adapters():
    assert JOB_DESCRIPTION_PARSER_VERSION == "job_description_parser:v15"
    assert SCORING_VERSION == "github_evidence_alignment:v2"
    assert EXTRACTOR_VERSION == "readme:v4"
    for py in (ROOT / "src").rglob("*.py"):
        assert "m11g22r" not in py.read_text(encoding="utf-8"), py
