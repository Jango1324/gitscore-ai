"""Milestone 11-G23 -- candidate-profile heading recovery (RESEARCH ONLY; production unchanged).

See docs/evaluation/MILESTONE_11_G23_CANDIDATE_PROFILE_HEADINGS.md. These tests pin the research record: the
frozen inputs and design, the P0 replica's fidelity to production v15, the recorded DEV / EVAL measurements,
the preserved EVAL gate failure, and the v15 failure mechanisms the milestone traced. They never assert any G23
policy as production behaviour.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "scripts", ROOT / "scripts" / "evaluation_lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import m11g23_eval as ev  # noqa: E402
import m11g23_harness as hz  # noqa: E402
import m11g23_policies as pol  # noqa: E402
import m11g23_validate_controls as val  # noqa: E402

from gitscore.jobs.parsing import parser as parser_mod  # noqa: E402
from gitscore.jobs.parsing import segmentation as seg  # noqa: E402
from gitscore.jobs.parsing.parser import parse_job_description_with_diagnostics  # noqa: E402

G23 = ROOT / "evaluation" / "m11g23"


def _json(name: str) -> dict:
    return json.loads((G23 / name).read_text(encoding="utf-8"))


def _sha(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


REPORT = _json("candidate_profile_report.json")
DESIGN = _json("policy_design_freeze.json")


# ---- frozen inputs and design ------------------------------------------------------------------------------------
@pytest.mark.parametrize("freeze", ["controls_dev_hash_freeze.json", "controls_eval_hash_freeze.json"])
def test_control_sets_and_guide_match_their_freezes(freeze):
    rec = _json(freeze)
    # The raw `sha256` was recorded at freeze time on this checkout's bytes; the canonical (CRLF -> LF) hash is the
    # line-ending-independent identity and is what a clean checkout under either core.autocrlf setting verifies.
    assert _sha(rec["artifact"]) == rec["sha256_canonical_crlf_to_lf"]
    assert _sha(rec["labelling_guide"]) == rec["labelling_guide_sha256_canonical_crlf_to_lf"]
    assert rec["registered_in_g14_manifest"] is False


def test_policy_design_freeze_matches_every_design_file():
    amended = {a["file"]: a for a in DESIGN["post_eval_amendments"]}
    assert set(amended) == {"scripts/evaluate_m11g23_candidate_profile_headings.py"}
    for rel, sha in DESIGN["design_files_sha256"].items():
        if rel in amended:
            assert amended[rel]["original_sha256"] == sha
            assert _sha(rel) == amended[rel]["amended_sha256_canonical_crlf_to_lf"], rel
        else:
            assert _sha(rel) == sha, rel
    for rel, sha in DESIGN["frozen_inputs_sha256_canonical_crlf_to_lf"].items():
        assert _sha(rel) == sha == REPORT["frozen_inputs"][rel], rel
    assert DESIGN["selected_policy"] == pol.SELECTED.name == REPORT["selected_policy"] == "P4_narrow_hybrid"


def test_dev_builder_reproduces_the_frozen_dev_set():
    import m11g23_build_dev_controls as b
    built = (json.dumps(b.DATA, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    assert built == (G23 / "controls_dev.json").read_bytes().replace(b"\r\n", b"\n")


@pytest.mark.parametrize("split", ["dev", "eval"])
def test_control_sets_are_structurally_valid(split):
    assert val.validate(json.loads(ev.SPLITS[split].read_text(encoding="utf-8"))) == []


# ---- harness safety -------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("split", ["dev", "eval"])
def test_p0_replica_equals_production_segmentation(split):
    assert hz.fidelity_mismatches([c["text"] for c in ev.load(split)], pol.P0) == []


def test_active_policy_is_always_restored():
    originals = (parser_mod.segment_description, seg.segment_description,
                 parser_mod.document_has_any_recognized_heading, seg.document_has_any_recognized_heading)
    with pytest.raises(RuntimeError):
        with hz.active(pol.SELECTED):
            assert parser_mod.segment_description is not originals[0]
            raise RuntimeError("boom")
    assert (parser_mod.segment_description, seg.segment_description,
            parser_mod.document_has_any_recognized_heading, seg.document_has_any_recognized_heading) == originals


def test_no_production_module_imports_g23_research_code():
    hits = subprocess.run(["git", "grep", "-l", "m11g23", "--", "src"], cwd=ROOT, capture_output=True, text=True)
    assert hits.stdout.strip() == ""


def test_production_versions_unchanged():
    from gitscore.assessment import SCORING_VERSION
    from gitscore.concepts.registry import CONCEPT_REGISTRY_VERSION
    from gitscore.evidence.extraction.readme import EXTRACTOR_VERSION
    from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION
    from gitscore.matching import MATCHER_VERSION
    assert (JOB_DESCRIPTION_PARSER_VERSION, SCORING_VERSION, MATCHER_VERSION, EXTRACTOR_VERSION,
            CONCEPT_REGISTRY_VERSION) == ("job_description_parser:v15", "github_evidence_alignment:v2",
                                          "requirement_matcher:v1", "readme:v6", 4)
    assert REPORT["versions"]["parser"] == "job_description_parser:v15"


# ---- the traced v15 mechanisms (Phase 1) ------------------------------------------------------------------------
def _kind(line: str):
    k = seg._classify_heading_line(line, line.strip())
    return None if k is None else k.name


def test_v15_heading_mechanisms():
    assert _kind("About you:") == "SKIP"                 # `^about` suppression: every line dropped silently
    assert _kind("What you bring:") == "UNKNOWN"         # no family: content admitted but no necessity
    assert _kind("Who We Are Looking For:") == "UNKNOWN"  # G6 exclusion keeps it out of SKIP, nothing more
    assert _kind("About you") is None                     # bare sentence case: not a heading at all
    assert _kind("Your Qualifications:") == "REQUIRED"   # already handled by the `qualif*` root
    assert _kind("Required qualifications") is None       # bare sentence-case conventional heading (EVAL finding)


def test_v15_content_outcomes_under_candidate_profile_headings():
    skip = parse_job_description_with_diagnostics("About you:\n- Experience with Python.\n")
    assert skip.profile.requirements == () and skip.unparsed_claims == ()          # lost, not even a diagnostic
    unknown = parse_job_description_with_diagnostics("What you bring:\n- Experience with Python.\n")
    assert unknown.profile.requirements == () and len(unknown.unparsed_claims) == 1  # visible diagnostic only


# ---- the recorded measurements reproduce --------------------------------------------------------------------------
@pytest.mark.parametrize("split", ["dev", "eval"])
def test_recorded_split_metrics_reproduce(split):
    for p in pol.POLICIES:
        assert ev.run(split, p)["metrics"] == REPORT[split][p.name]["metrics"], (split, p.name)


def test_recorded_eval_gate_failure_is_preserved():
    gates = REPORT["eval_gates_selected"]
    assert gates["all_pass"] is False
    assert gates["G1_recall"]["pass"] is False
    assert gates["G1_recall"]["p0"] == [53, 145] and gates["G1_recall"]["selected"] == [62, 145]
    assert all(gates[k]["pass"] for k in gates if k not in ("G1_recall", "all_pass"))
    assert REPORT["acceptance_gates"] == DESIGN["acceptance_gates"]


def test_historical_non_candidate_profile_sections_unchanged_for_every_policy():
    assert REPORT["historical"]["p0_replica_dump_equals_production"] is True
    for name in ("P1_cp_headings", "P2_section_aware", "P3_cp_headings_intent", "P4_narrow_hybrid"):
        h = REPORT["historical"][name]
        assert set(h["changed_public_sections"]) <= {"controls/g20_dev", "controls/g20_holdout", "corpora/g6"}, name
        assert h["m10e_g3_live_unchanged"] and h["frozen_8c_and_fixture_scoring_unchanged"], name


def test_posthoc_file_is_marked_non_confirmatory():
    post = _json("eval_posthoc_diagnostics.json")
    assert post["status"].startswith("POST-HOC, NON-CONFIRMATORY")
    assert post["selected_policy"] == "P4_narrow_hybrid"
    assert sum(post["by_mechanism"].values()) == post["unrecovered_qualification_units"]


def test_private_aggregates_are_totals_only():
    text = (G23 / "private_candidate_profile_aggregates.json").read_text(encoding="utf-8")
    assert "per_posting" not in text and '"_per"' not in text

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k != "note":
                    walk(v)
        else:
            assert not isinstance(o, (str, list)), o
    walk(json.loads(text))
