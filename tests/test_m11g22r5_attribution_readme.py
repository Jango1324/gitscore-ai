"""Milestone 11-G22-R5 -- attribution-aware README evidence research (RESEARCH tests; readme:v5 NOT implemented).

G22-R5 changes no production code and no registry data. These tests pin:
  * the R5 DEV and fresh freezes (G14 portable hashes; registered at the authorized research commit with their
    original freeze-time hashes, 25 -> 27, additively over the G22-R4 commit 39b570c) and the chronology
    DEV frozen -> policy design frozen -> fresh set frozen, with the frozen policy files unchanged;
  * that the R5 candidates are attribution-only (no homonym lexicon, no negation) and apply to every alias;
  * Markdown-aware and multi-occurrence behaviour (setext sections, quotes, link annotations, planning checklists,
    fall-through to a later genuine occurrence, overlap blocking as a separate finding);
  * the measured held-out outcome, exactly as recorded;
  * that the public report holds no canonical-manifest state, and the counts-only private aggregates.
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
import m11g22r5_policies as p5  # noqa: E402
from gitscore.assessment import SCORING_VERSION  # noqa: E402
from gitscore.concepts.registry import CONCEPT_REGISTRY_VERSION, default_registry  # noqa: E402
from gitscore.evidence.extraction.readme import EXTRACTOR_VERSION, evidence_from_readme  # noqa: E402
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION  # noqa: E402
from gitscore.matching import MATCHER_VERSION  # noqa: E402

DATA = ROOT / "evaluation" / "m11g22r5"
DEV_SHA = "c415966a0112ed2324c7285805594eafa41d73fc7bc9699fcaa74f80fb3a9718"
LIVE = (JOB_DESCRIPTION_PARSER_VERSION, EXTRACTOR_VERSION, MATCHER_VERSION, SCORING_VERSION) == (
    "job_description_parser:v15", "readme:v4", "requirement_matcher:v1", "github_evidence_alignment:v2")
only_measured = pytest.mark.skipif(not LIVE, reason="documents the measured readme:v4 / v15 / v1 / v2 production")


def _extracted(policy, text: str, concept: str) -> bool:
    with p5.mechanism(), p2.applied(policy):
        ev = evidence_from_readme("o", "r", text if text.startswith("#") else f"# demo\n\n{text}\n", "README.md")
    return concept in {e.concept_id for e in ev}


# ---- freezes, chronology ---------------------------------------------------------------------------------------
PARENT = "39b570c83b09cb62db49d664fcae062ae9731c02"  # the G22-R4 research commit


def _assert_registered(data: str, record: str, sha: str) -> None:
    """Registered at the authorized research commit with the ORIGINAL freeze-time hash (25 -> 27)."""
    rec = json.loads((DATA / record).read_text(encoding="utf-8"))
    assert "NOT registered" in rec["note"]  # the freeze record keeps its freeze-time wording; never rewritten
    rel = f"evaluation/m11g22r5/{data}"
    assert gi.verify_frozen_file(rel, f"evaluation/m11g22r5/{record}").historical_raw_sha256 == sha
    entry = json.loads(gi.DEFAULT_MANIFEST.read_text(encoding="utf-8"))["entries"][rel]
    assert (entry["freeze_record"], entry["historical_raw_sha256"], entry["canonical_sha256"],
            entry["historical_newline_form"], entry["canonical_length_bytes"]) == \
        (f"evaluation/m11g22r5/{record}", sha, sha, "lf", rec["length_bytes"])
    assert entry["attested_from_commit"] == f"staged-for-commit-on-parent-{PARENT}"


def test_dev_freeze_is_portable_and_registered_with_its_original_hash():
    rec = json.loads((DATA / "dev_hash_freeze.json").read_text(encoding="utf-8"))
    assert rec["sha256"] == rec["sha256_lf_normalized"] == DEV_SHA and rec["canonical_contract"] == gi.CONTRACT
    assert gi.sha256(gi.canonical_bytes((DATA / "dev_controls.json").read_bytes())) == DEV_SHA
    _assert_registered("dev_controls.json", "dev_hash_freeze.json", DEV_SHA)


def test_design_freeze_files_unchanged_and_ordered_after_dev():
    design = json.loads((DATA / "policy_design_freeze.json").read_text(encoding="utf-8"))
    for f, sha in design["files"].items():
        assert gi.sha256(gi.canonical_bytes((ROOT / f).read_bytes())) == sha, f
    dev = json.loads((DATA / "dev_hash_freeze.json").read_text(encoding="utf-8"))["frozen_at_utc"]
    assert dev < design["frozen_at_utc"]
    assert design["selected_candidate"] == p5.D_S.name and design["post_hoc_changes"] == []
    assert design["fresh_set_state_at_freeze"]["author_finished"] is False
    # the reused R4 module is the exact file frozen and committed by G22-R4
    assert design["files"]["scripts/evaluation_lib/m11g22r4_policies.py"] == \
        "e56c518c127a60ee8d457bb24962f8dbd36aa0d970b0177121a63f498b963ce4"


def test_manifest_registration_is_additive_over_the_g22r4_commit():
    """Pinned historical state: at the G22-R4 commit 39b570c the manifest had 25 entries and neither R5 set; every one
    of those 25 entries is still present field for field, the manifest metadata is unchanged, both R5 sets are now
    registered, and every current entry verifies. Exact coverage of tracked freezes is enforced by
    test_m11g14_gold_integrity's inventory rule."""
    import subprocess
    parent = json.loads(subprocess.run(["git", "show", f"{PARENT}:evaluation/integrity/canonical_hash_manifest.json"],
                                       cwd=ROOT, check=True, capture_output=True).stdout)
    r5 = {"evaluation/m11g22r5/dev_controls.json", "evaluation/m11g22r5/fresh_validation_controls.json"}
    assert len(parent["entries"]) == 25 and not (r5 & set(parent["entries"]))
    manifest = json.loads(gi.DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    assert all(manifest["entries"][k] == v for k, v in parent["entries"].items())
    assert {k: v for k, v in manifest.items() if k != "entries"} == {k: v for k, v in parent.items() if k != "entries"}
    assert r5 <= set(manifest["entries"]) and len(manifest["entries"]) >= 27
    assert "evaluation/m11g22r5/policy_design_freeze.json" not in manifest["entries"]  # provenance, not a control set
    for frozen, e in manifest["entries"].items():
        gi.verify_frozen_file(frozen, e["freeze_record"])


def test_research_adapters_are_not_imported_by_production():
    for path in (ROOT / "src").rglob("*.py"):
        assert "m11g22r5" not in path.read_text(encoding="utf-8"), path


@only_measured
def test_production_versions_unchanged():
    assert (JOB_DESCRIPTION_PARSER_VERSION, SCORING_VERSION, MATCHER_VERSION, EXTRACTOR_VERSION,
            CONCEPT_REGISTRY_VERSION) == ("job_description_parser:v15", "github_evidence_alignment:v2",
                                          "requirement_matcher:v1", "readme:v4", 4)


# ---- attribution-only scope ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("text,concept", [
    ("Keeps bike chains free of rust.", "language.rust"),        # ordinary English: out of scope
    ("Helps teams react quickly to alerts.", "framework.react"),  # ordinary English: out of scope
    ("No Docker needed.", "infra.docker"),                         # negation: out of scope
])
def test_candidates_do_not_reject_non_attribution_mentions(text, concept):
    for policy in p5.CANDIDATES:
        assert _extracted(policy, text, concept), policy.name


@pytest.mark.parametrize("text,concept,layer", [
    ("A tiny REST router for Go, inspired by FastAPI.", "framework.fastapi", "A"),
    ("Spanish translation of the official PostgreSQL documentation.", "database.postgresql", "A"),
    ("We moved off Redis in 2024.", "database.redis", "B"),
    ("We plan to add Kubernetes manifests later.", "infra.kubernetes", "C"),
    ("From the cachelib README:\n\n> cachelib stores entries in Redis.", "database.redis", "D"),
])
def test_each_layer_rejects_its_attribution_kind_for_non_ambiguous_aliases(text, concept, layer):
    order = ["A", "B", "C", "D"]
    for policy, name in zip(p5.CANDIDATES[:4], order):
        assert _extracted(policy, text, concept) is (order.index(name) < order.index(layer)), (policy.name, text)
    assert _extracted(p2.A, text, concept)


def test_every_readme_safe_alias_still_extractable_under_every_candidate():
    reg = default_registry()
    for policy in p5.CANDIDATES:
        for c in reg.all_concepts():
            for alias in c.readme_safe_aliases():
                assert _extracted(policy, f"This project is built with {alias}.", c.concept_id), (policy.name, alias)


# ---- Markdown and multi-occurrence -------------------------------------------------------------------------------
def test_setext_section_boundary_recovers_evidence_production_loses():
    text = "# g\n\n## Related projects\n\n- ripgrep (Rust)\n\nDevelopment\n-----------\n\nThis tool is written in Rust.\n"
    assert not _extracted(p2.A, text, "language.rust")      # production: 'related projects' never closes
    assert not _extracted(p5.D, text, "language.rust")
    assert _extracted(p5.D_S, text, "language.rust")


def test_project_quote_is_kept_and_attributed_quote_is_rejected():
    assert _extracted(p5.D_S, "# f\n\nCSV tools.\n\n> **Note:** this project requires Python 3.11.\n",
                      "language.python")
    assert not _extracted(p5.D_S, "# n\n\nNotices.\n\nFrom the cachelib README:\n\n> cachelib stores entries in "
                                  "Redis.\n", "database.redis")


def test_unchecked_task_is_future_only_under_a_planning_heading():
    assert not _extracted(p5.D_S, "# t\n\n## Roadmap\n\n- [ ] TypeScript definitions\n", "language.typescript")
    assert _extracted(p5.D_S, "# t\n\n## Database\n\n- [ ] `schema.sql` has been run in the SQL editor\n",
                      "language.sql")


def test_invalid_mention_does_not_block_a_later_valid_one_and_provenance_moves():
    text = "# grepx\n\nA faster grep, inspired by ripgrep's Rust implementation. This tool is also written in Rust.\n"
    with p5.mechanism(), p2.applied(p5.D_S):
        (ev,) = [e for e in evidence_from_readme("o", "r", text, "README.md") if e.concept_id == "language.rust"]
    assert "written in Rust" in ev.raw_observation


def test_overlap_blocking_is_a_separate_finding_not_part_of_the_candidate():
    text = "# a\n\nA React Native app. The web dashboard uses React.\n"
    assert not _extracted(p2.A, text, "framework.react") and not _extracted(p5.D_S, text, "framework.react")
    assert _extracted(p5.O, text, "framework.react")


def test_fenced_code_is_never_attributed():
    text = "# r\n\nA Go tool.\n\nFrom the polars docs:\n\n```python\nimport pandas as pd\n```\n"
    assert p5.markdown_reason(text, text.index("pandas"), text.index("pandas") + 6) is None


# ---- held-out set and recorded outcome -----------------------------------------------------------------------------
FRESH_SHA = "697fde84c5632bba991f5e76903aad750405bac3931f9c9d119f61710ca0f4c3"


@pytest.fixture(scope="module")
def report():
    return json.loads((DATA / "attribution_readme_report.json").read_text(encoding="utf-8"))


def test_fresh_set_frozen_after_the_design_and_registered_with_its_original_hash():
    rec = json.loads((DATA / "fresh_hash_freeze.json").read_text(encoding="utf-8"))
    assert rec["sha256"] == rec["sha256_lf_normalized"] == FRESH_SHA
    assert gi.sha256(gi.canonical_bytes((DATA / "fresh_validation_controls.json").read_bytes())) == FRESH_SHA
    design = json.loads((DATA / "policy_design_freeze.json").read_text(encoding="utf-8"))
    assert design["frozen_at_utc"] < rec["frozen_at_utc"]
    _assert_registered("fresh_validation_controls.json", "fresh_hash_freeze.json", FRESH_SHA)
    prov = json.loads((DATA / "fresh_author_provenance.json").read_text(encoding="utf-8"))
    assert "NOT human-independent" in prov["author"] and prov["author_saw_previous_examples"] is False
    assert prov["author_reply_restriction"] == "file paths and case counts only; no case content"
    assert prov["pre_freeze_checks"]["counts"] == {"cases": 96, "labels_without_mention": 0, "unlabelled_mentions": 0}


@only_measured
def test_held_out_outcome_is_recorded_as_measured(report):
    acc = report["acceptance"]
    assert acc["policy"] == "D_S_setext_sections" and acc["passed"] is False
    assert {k: v[2] for k, v in acc["checks"].items()} == {
        "G1_genuine_readme_use_retention": True, "G2_true_supported_retention": True,
        "G3_no_new_false_supported": True, "G4_corroborated": True, "G5_no_non_attribution_change": True,
        "G6_g19_capability": True, "G7_no_parser_regression": True, "G8_attribution_false_supported_reduction": False}
    assert acc["checks"]["G8_attribution_false_supported_reduction"][:2] == [39, 49]
    assert acc["overall_false_supported"] == [42, 52]
    fresh = report["fresh"]["results"]["D_S_setext_sections"]["aggregate"]
    assert fresh["use_claims_retained"] == [95, 95] and fresh["corroborated_supported"] == [33, 33]


@only_measured
def test_held_out_primary_result_reproduces_for_the_frozen_policy(report):
    """A deterministic re-run of the SAME frozen policy (not a new assessment) reproduces the recorded aggregates."""
    import evaluate_m11g22r5_attribution_readme as e5
    ctrl = json.loads((DATA / "fresh_validation_controls.json").read_text(encoding="utf-8"))["controls"]
    with p5.mechanism():
        for policy in (p2.A, p5.D_S):
            res = [e5.run_control(c, policy) for c in ctrl]
            rec = report["fresh"]["results"][policy.name]
            assert e5._att_fs(res) == rec["attribution_false_supported"]
            agg = e5.h.aggregate(res, ctrl)
            for k in ("false_supported", "use_claims_retained", "true_supported", "corroborated_supported"):
                assert agg[k] == rec["aggregate"][k], (policy.name, k)


def test_public_report_holds_no_canonical_manifest_state(report):
    text = json.dumps(report)
    assert "registered_in_manifest" not in text and "historical_manifest" not in text
    assert "canonical_hash_manifest" not in text


def test_private_aggregates_are_integer_counts_only():
    agg = json.loads((DATA / "private_attribution_readme_aggregates.json").read_text(encoding="utf-8"))

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k != "note":
                    yield from walk(v)
        else:
            yield o
    assert all(isinstance(v, int) for v in walk({k: v for k, v in agg.items() if k != "note"}))
    assert all(v["postings_changed"] == 0 for k, d in agg.items() if k != "note" for v in d.values())
