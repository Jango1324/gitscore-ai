"""Milestone 11-G20 -- false qualification admission (research only).

Guards the frozen G20 controls and policy design, the fidelity of the
research replica to production v13, the reproduction of the known
defects on the REAL production parser, the determinism of the committed
report, the recommended slice's compatibility invariants, publication
safety, and that NO production behaviour changed (parser v13, scoring v2).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "scripts", REPO_ROOT / "scripts" / "evaluation_lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import gold_integrity as gi  # noqa: E402
import m11g20_admission as adm  # noqa: E402
import m11g20_historical as hist  # noqa: E402
import m11g20_policies as pol  # noqa: E402
import m11g20_posthoc as post  # noqa: E402
from gitscore.assessment import SCORING_VERSION  # noqa: E402
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION, parse_job_description  # noqa: E402

G20 = REPO_ROOT / "evaluation" / "m11g20"
REPORT = G20 / "admission_report.json"
PRIVATE = G20 / "private_admission_aggregates.json"


@pytest.fixture(scope="module")
def report() -> dict:
    return json.loads(REPORT.read_text(encoding="utf-8"))


# ---- freezes ----------------------------------------------------------------------------------------
@pytest.mark.parametrize("split", ["dev", "holdout"])
def test_control_freeze_verifies(split):
    res = gi.verify_frozen_file(adm.CONTROLS[split], adm.FREEZES[split])
    assert res.method in ("raw", "canonical")


def test_policy_design_freeze_verifies():
    rec = json.loads((G20 / "policy_design_freeze.json").read_text(encoding="utf-8"))
    for rel, digest in rec["sources"].items():
        assert hashlib.sha256((REPO_ROOT / rel).read_bytes().replace(b"\r\n", b"\n")).hexdigest() == digest, rel


def test_builder_refuses_to_change_frozen_controls(tmp_path, monkeypatch):
    import m11g20_build_controls as b

    out = tmp_path / "dev.json"
    out.write_bytes(b"{}")
    monkeypatch.setattr(b, "SETS", {"dev": (out, tmp_path / "f.json"), "holdout": (out, tmp_path / "g.json")})
    with pytest.raises(SystemExit):
        b.main()


# ---- control-set integrity ------------------------------------------------------------------------
def test_controls_are_well_formed_and_splits_are_disjoint():
    dev, hold = adm.load_controls("dev"), adm.load_controls("holdout")
    assert len(dev) == 71 and len(hold) == 36
    assert sum(len(c["units"]) for c in dev) == 103 and sum(len(c["units"]) for c in hold) == 46
    assert not {c["id"] for c in dev} & {c["id"] for c in hold}
    assert not {c["text"] for c in dev} & {c["text"] for c in hold}
    for c in dev + hold:
        for u in c["units"]:
            assert c["text"].count(u["span"]) == 1
            assert (u["nec"] is None) == (not u["qual"])


def test_controls_document_provenance_honestly():
    for split in ("dev", "holdout"):
        doc = json.loads(adm.CONTROLS[split].read_text(encoding="utf-8"))
        assert "not blind or independently validated" in doc["authorship_disclosure"]
        assert "BEFORE the production parser ran" in doc["label_timing"]


# ---- replica fidelity -----------------------------------------------------------------------------
def test_v13_replica_equals_production_on_controls_and_frozen_corpora():
    texts = [c["text"] for s in ("dev", "holdout") for c in adm.load_controls(s)]
    corp = hist.tracked_corpora()
    texts += [t for name in ("g16", "g18", "m10e", "g6") for _, t, _ in corp[name]]
    assert adm.fidelity_check(texts) == []


# ---- known defects reproduce on the REAL production parser ------------------------------------------
def _rows(text):
    return parse_job_description(text).requirements


V13 = JOB_DESCRIPTION_PARSER_VERSION == "job_description_parser:v13"


def test_g18_control_25_narrative_becomes_required_rows():
    rows = _rows("About us: we use Python, Terraform and Docker.")
    if not V13:  # M11-G21 (v14) implements the fix G20 recommended: no requirement at all
        assert rows == ()
        return
    ids = {r.concept_id for r in rows}
    assert {"language.python", "infra.docker", "unresolved:terraform"} <= ids
    assert all(r.necessity.value == "required" for r in rows)


def test_g16_053_responsibility_is_a_required_placeholder():
    rows = _rows("You will maintain services written in Python or Go, and deploy them with Docker.")
    if not V13:  # M11-G21 (v14): declined (UnparsedClaim), no REQUIRED placeholder
        assert rows == ()
        return
    assert len(rows) == 1 and rows[0].category == "alternative_requirement" and rows[0].necessity.value == "required"


def test_generic_words_become_concepts():
    assert {r.concept_id for r in _rows("Requirements:\n- Ability to react quickly to production incidents.")} \
        == {"framework.react"}
    ids = {r.concept_id for r in _rows("Requirements:\n- Experience with SQL, attention to detail, and curiosity.")}
    assert "unresolved:curiosity" in ids


def test_about_you_heading_suppresses_genuine_qualifications():
    assert _rows("About you:\n- 4+ years of experience with Java.\n- Experience with Kafka and Kubernetes.") == ()


# ---- committed report is reproducible ----------------------------------------------------------------
@pytest.mark.parametrize("split", ["dev", "holdout"])
@pytest.mark.parametrize("policy", [adm.POLICY_V13, post.POLICY_B1NR, pol.POLICY_C])
def test_report_aggregates_reproduce(report, split, policy):
    _, agg = adm.run_split(split, policy)
    if V13 or policy is not adm.POLICY_V13:
        assert report["controls"][split][policy.name]["aggregate"] == agg
        return
    # M11-G21 (v14): the replica's "v13" policy calls the live production parser, which now IS
    # B1NR -- so it must reproduce G20's frozen B1NR research aggregate exactly (port fidelity),
    # while the frozen v13 aggregate stays in the committed report as the v13 research result.
    assert report["controls"][split][post.POLICY_B1NR.name]["aggregate"] == agg
    assert report["controls"][split]["v13"]["aggregate"] != agg


def test_report_headline_numbers(report):
    dev, hold = report["controls"]["dev"], report["controls"]["holdout"]
    assert dev["v13"]["aggregate"]["1_false_admissions"]["units_with_any_row"] == 26
    assert hold["v13"]["aggregate"]["1_false_admissions"]["units_with_any_row"] == 16
    rec = post.POLICY_B1NR.name
    assert dev[rec]["aggregate"]["1_false_admissions"]["units_with_any_row"] == 0
    assert hold[rec]["aggregate"]["1_false_admissions"]["units_with_any_row"] == 1
    for split in (dev, hold):  # the recommended slice never loses a represented qualification
        assert split[rec]["aggregate"]["recall"]["unit_recall"] >= split["v13"]["aggregate"]["recall"]["unit_recall"]


# ---- recommended slice: compatibility invariants -----------------------------------------------------
def test_recommended_slice_has_no_historical_gold_regression_and_keeps_g17():
    corp = hist.tracked_corpora()
    for name in ("g15", "g16", "g18", "m10d", "m10e", "g6", "g7"):
        assert hist.corpus_impact(corp[name], post.POLICY_B1NR)["gold_regressed_ids"] == [], name
    assert hist.g17_containment_preserved(post.POLICY_B1NR)["violations"] == 0


def test_rejected_require_intent_variant_destroys_bare_lists():
    """The evidence behind 'never decline merely for lacking a qualification frame'."""
    r = hist.corpus_impact(hist.tracked_corpora()["m10d"], pol.POLICY_A0)
    assert len(r["gold_regressed_ids"]) == 5


def test_heading_component_would_change_frozen_heading_labels(report):
    hk = report["historical_impact"][pol.POLICY_C.name]["g6_g7_heading_kind_gold"]
    assert hk["g6"]["gold_agreement_v13"] - hk["g6"]["gold_agreement_policy"] == 16
    assert hk["g7"]["gold_agreement_v13"] - hk["g7"]["gold_agreement_policy"] == 2


# ---- production untouched -------------------------------------------------------------------------------
def test_versions_unchanged():
    # G20 itself was research-only on v13; M11-G21 then bumped the parser to v14, M11-G22-Q to v15.
    assert JOB_DESCRIPTION_PARSER_VERSION in ("job_description_parser:v13", "job_description_parser:v14",
                                              "job_description_parser:v15")
    assert SCORING_VERSION == "github_evidence_alignment:v2"


def test_production_source_unchanged_from_head():
    r = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "src"], cwd=REPO_ROOT)
    assert r.returncode == 0, "G20 is research-only: src/ must equal HEAD"


def test_research_modules_never_imported_by_production():
    for py in (REPO_ROOT / "src").rglob("*.py"):
        assert "m11g20" not in py.read_text(encoding="utf-8"), py


# ---- publication safety -----------------------------------------------------------------------------------
def test_private_aggregates_are_counts_only():
    def walk(obj, key=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, k)
        else:
            assert not isinstance(obj, list), key
            assert not isinstance(obj, str) or key in ("note", "description"), key
    walk(json.loads(PRIVATE.read_text(encoding="utf-8")))


@pytest.mark.skipif(not hist.private_available(), reason="private sources not present")
def test_no_private_text_in_tracked_g20_artifacts():
    needles = set()
    for texts in hist.private_texts().values():
        for t in texts:
            needles.update(line.strip() for line in t.splitlines() if len(line.strip()) >= 40)
    artifacts = [*G20.glob("*.json"), REPO_ROOT / "docs/evaluation/MILESTONE_11_G20_FALSE_QUALIFICATION_ADMISSION.md",
                 *(REPO_ROOT / "scripts" / "evaluation_lib").glob("m11g20_*.py"),
                 REPO_ROOT / "scripts" / "evaluate_m11g20_false_qualification.py"]
    blob = "\n".join(p.read_text(encoding="utf-8") for p in artifacts if p.exists())
    assert not [n for n in needles if n in blob]
