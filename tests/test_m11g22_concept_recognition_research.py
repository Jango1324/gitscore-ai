"""Milestone 11-G22 -- concept recognition precision RESEARCH tests.

G22 changes no production code. These tests pin:
  * the frozen G22 control sets and the policy-design freeze record;
  * the research adapters' fidelity (BASE == unpatched production; patches always restored);
  * the live v14 failures G22 documents (version-gated: they describe parser v14 only);
  * the measured behaviour of the candidate policies on the key near-neighbour controls;
  * the M10E-g3 evidence (frozen gold untouched);
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
import m11g22_concepts as h  # noqa: E402
import m11g22_policies as pol  # noqa: E402
import m11g22_posthoc as ph  # noqa: E402
from gitscore.assessment import SCORING_VERSION, assess_job  # noqa: E402
from gitscore.concepts.registry import default_registry, is_unresolved_concept_id, is_valid_concept_id  # noqa: E402
from gitscore.jobs.parsing import alternatives as alt_mod  # noqa: E402
from gitscore.jobs.parsing import parser as parser_mod  # noqa: E402
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION, parse_job_description_with_diagnostics  # noqa: E402
from gitscore.matching import match_job  # noqa: E402
from m11g15_or_scoring import candidate_profile  # noqa: E402

DATA = ROOT / "evaluation" / "m11g22"
V14 = JOB_DESCRIPTION_PARSER_VERSION == "job_description_parser:v14"
only_v14 = pytest.mark.skipif(not V14, reason="documents the live parser v14 behaviour G22 measured")
REQ = "Requirements:\n- "


def _rows(text, policy=pol.BASE):
    return [(h.members(r), r.category, r.necessity.value) for r in h.parse(text, policy).profile.requirements]


def _ids(text, policy=pol.BASE):
    return sorted({i for m, _, _ in _rows(text, policy) for i in m})


# ---- freezes ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("split", ["dev", "eval"])
def test_control_sets_are_frozen_and_registered_with_their_original_hashes(split):
    original = {"dev": "86ec710fc72b9196b5353df1b51bdd3057343784560a34af04104badf42b92f9",
                "eval": "29b3ea2acf1363fa6c3c7809581bd251a691e724ec3b6f7ba899504081835cc3"}[split]
    rel = f"evaluation/m11g22/concept_controls_{split}.json"
    record = f"evaluation/m11g22/{split}_hash_freeze.json"
    res = gi.verify_frozen_file(rel, record)
    assert res.method in ("raw", "canonical") and res.historical_raw_sha256 == original
    manifest = json.loads((ROOT / "evaluation/integrity/canonical_hash_manifest.json").read_text(encoding="utf-8"))
    entry = manifest["entries"][rel]
    assert (entry["freeze_record"], entry["historical_raw_sha256"], entry["canonical_sha256"],
            entry["historical_newline_form"]) == (record, original, original, "lf")
    assert len(manifest["entries"]) == 17


def test_freeze_hashes_are_the_recorded_values():
    dev = json.loads((DATA / "dev_hash_freeze.json").read_text(encoding="utf-8"))
    ev = json.loads((DATA / "eval_hash_freeze.json").read_text(encoding="utf-8"))
    assert dev["sha256"] == "86ec710fc72b9196b5353df1b51bdd3057343784560a34af04104badf42b92f9"
    assert ev["sha256"] == "29b3ea2acf1363fa6c3c7809581bd251a691e724ec3b6f7ba899504081835cc3"


def test_policy_design_freeze_records_the_frozen_design_and_the_post_hoc_fidelity_fix():
    rec = json.loads((DATA / "policy_design_freeze.json").read_text(encoding="utf-8"))
    assert rec["eval_controls_sha256"] == "29b3ea2acf1363fa6c3c7809581bd251a691e724ec3b6f7ba899504081835cc3"
    concepts = ROOT / "scripts/evaluation_lib/m11g22_concepts.py"
    policies = ROOT / "scripts/evaluation_lib/m11g22_policies.py"
    assert gi.sha256(gi.canonical_bytes(concepts.read_bytes())) == \
        rec["files"]["scripts/evaluation_lib/m11g22_concepts.py"]["sha256_lf"]
    (change,) = rec["post_hoc_changes"]
    assert change["file"] == "scripts/evaluation_lib/m11g22_policies.py"
    assert gi.sha256(gi.canonical_bytes(policies.read_bytes())) == change["sha256_lf_after"]


# ---- control-set integrity ------------------------------------------------------------------------
def test_control_sets_are_distinct_well_formed_and_disclosed():
    dev, ev = h.load_controls("dev"), h.load_controls("eval")
    assert (len(dev), len(ev)) == (46, 44)
    ids = [c["id"] for c in dev + ev]
    assert len(ids) == len(set(ids))
    assert {c["split"] for c in dev} == {"dev"} and {c["split"] for c in ev} == {"eval"}
    assert not {c["text"] for c in dev} & {c["text"] for c in ev}
    by_id = {c["id"]: c for c in dev + ev}
    for c in dev + ev:
        assert c["pair"] is None or c["pair"] in by_id
        for k in c["expected_concepts"]:
            assert k["necessity"] in ("required", "preferred")
            assert all(is_valid_concept_id(i) for i in k["members"]), c["id"]
        if not c["is_qualification"]:
            assert c["expected_concepts"] == []
    for split in ("dev", "eval"):
        doc = json.loads((DATA / f"concept_controls_{split}.json").read_text(encoding="utf-8"))
        assert "NOT an independent validation set" in doc["authorship_disclosure"]


# ---- adapter fidelity -----------------------------------------------------------------------------
def test_base_adapter_is_byte_identical_to_unpatched_production():
    texts = [c["text"] for c in h.load_controls("dev") + h.load_controls("eval")]
    for t in texts:
        assert repr(parse_job_description_with_diagnostics(t)) == repr(h.parse(t, pol.BASE))


def test_every_policy_restores_the_production_functions():
    names = ("decide_qualification_intent", "find_conservative_unknown_terms", "find_concept_mentions",
             "classify_alternative_claim")
    before = [getattr(parser_mod, n) for n in names] + [alt_mod.find_concept_mentions]
    for p in (*pol.POLICIES, *ph.POSTHOC):
        h.parse(REQ + "Experience with Go or Golang, React, and curiosity.", p)
    assert [getattr(parser_mod, n) for n in names] + [alt_mod.find_concept_mentions] == before
    assert pol._CURRENT_CLAIM == []


def test_policies_never_change_admission_or_span_provenance():
    from gitscore.jobs.parsing.qualification_intent import decide_qualification_intent
    from gitscore.jobs.parsing.segmentation import segment_description
    for c in h.load_controls("dev") + h.load_controls("eval"):
        claims = segment_description(c["text"])
        base = [decide_qualification_intent(cl.text, cl.section_kind) for cl in claims]
        for p in (*pol.POLICIES, *ph.POSTHOC):
            with pol.applied(p):
                now = [parser_mod.decide_qualification_intent(cl.text, cl.section_kind) for cl in claims]
            assert [(d.admit, d.role, d.frame) for d in now] == [(d.admit, d.role, d.frame) for d in base]
            for d, b, cl in zip(now, base, claims):  # only ever blanks: same length, untouched elsewhere
                scoped = d.scoped_text
                if scoped is not None:
                    ref = b.scoped_text or cl.text
                    assert len(scoped) == len(ref)
                    assert all(x == y or x == " " for x, y in zip(scoped, ref))
            for r in h.parse(c["text"], p).profile.requirements:
                assert c["text"][r.source_span.start:r.source_span.end] == r.original_text


# ---- live v14 failures (documented, version-gated) -------------------------------------------------
@only_v14
def test_v14_recognises_ordinary_verbs_as_registered_frameworks_and_counts_them():
    parsed = parse_job_description_with_diagnostics(REQ + "Ability to react quickly to production incidents.")
    a = assess_job(match_job(candidate_profile(["framework.react"]), parsed.profile))
    (m,) = a.match_analysis.requirement_matches
    assert m.requirement.concept_id == "framework.react"
    assert a.counts_toward_alignment(m) and m.status.value == "supported" and a.alignment_score == 100


@only_v14
@pytest.mark.parametrize("text,fabricated", [
    (REQ + "Experience with SQL, attention to detail, and curiosity.", "unresolved:curiosity"),
    ("Experience with AWS is required. Alternatively, Docker experience is acceptable.", "unresolved:alternatively"),
    (REQ + "Python, teamwork, and Docker.", "unresolved:teamwork"),
    (REQ + "Solid React experience, including hooks and context.", "unresolved:context"),
    (REQ + "Experience with Go, Docker, and Kubernetes.", "unresolved:go"),
])
def test_v14_fabricates_unresolved_concepts_that_scoring_v2_excludes(text, fabricated):
    parsed = parse_job_description_with_diagnostics(text)
    a = assess_job(match_job(candidate_profile([]), parsed.profile))
    (m,) = [m for m in a.match_analysis.requirement_matches if m.requirement.concept_id == fabricated]
    assert a.alignment_exclusion_reason(m).value == "unresolved_technology"


@only_v14
def test_v14_turns_equivalent_aliases_into_a_not_assessable_placeholder():
    assert _rows(REQ + "Experience with Go or Golang.") == [((), "alternative_requirement", "required")]
    assert _rows(REQ + "Experience with Postgres or PostgreSQL.") == [((), "alternative_requirement", "required")]
    assert _rows(REQ + "Experience with Go.") == [((), "unresolved_requirement", "required")]


# ---- candidate policies on near-neighbour controls ------------------------------------------------
def test_option_a_removes_lowercase_verb_frames_but_keeps_the_library():
    assert _ids(REQ + "Ability to react quickly to production incidents.", pol.A) == []
    assert _ids(REQ + "Ability to express complex technical ideas clearly.", pol.A) == []
    assert _ids(REQ + "Experience with React and modern frontend tooling.", pol.A) == ["framework.react"]
    # documented limit: a claim-initial capital carries no casing signal
    assert _ids(REQ + "Swift decision-making in a fast-paced environment.", pol.A) == ["language.swift"]


def test_option_b_requires_a_technical_cue_for_reviewed_ambiguous_aliases_only():
    assert _ids(REQ + "Swift decision-making in a fast-paced environment.", pol.B) == []
    assert _ids(REQ + "Experience building iOS applications in Swift.", pol.B) == ["language.swift"]
    assert _ids(REQ + "Ability to come out of your shell and present to clients.", pol.B) == []
    assert _ids(REQ + "Experience writing shell scripts for automation.", pol.B) == ["language.shell"]
    assert _ids("Nice to have:\n- React, Express, Swift", pol.B) == \
        ["framework.express", "framework.react", "language.swift"]
    # measured recall cost of the frozen design (recovered only by the post-hoc B2)
    assert _ids(REQ + "Ruby and Rails experience.", pol.B) == []
    assert _ids(REQ + "Ruby and Rails experience.", ph.B2) == ["language.ruby"]


def test_option_c_rejects_abstract_fragments_but_keeps_genuine_unknown_technologies():
    assert _ids(REQ + "Experience with SQL, attention to detail, and curiosity.", pol.C) == ["language.sql"]
    assert _ids(REQ + "Python, teamwork, and Docker.", pol.C) == ["infra.docker", "language.python"]
    assert _ids(REQ + "Experience with Python, numpy, and scipy.", pol.C) == \
        ["language.python", "unresolved:numpy", "unresolved:scipy"]
    assert "unresolved:unity" in _ids(REQ + "Experience with C#, Unity, and Blender.", pol.C)
    # measured cost of the frozen discourse-adverb gate; the post-hoc C2 keeps it
    assert "unresolved:plotly" not in _ids(REQ + "Plotly, Dash, and Python.", pol.C)
    assert "unresolved:plotly" in _ids(REQ + "Plotly, Dash, and Python.", ph.C2)
    # documented residual: a lowercase common noun is indistinguishable from a lowercase package name
    assert "unresolved:context" in _ids(REQ + "Solid React experience, including hooks and context.", pol.C)


def test_option_q_collapses_equivalent_aliases_only():
    assert _rows(REQ + "Experience with Go or Golang.", pol.Q) == [(("language.go",), "language", "required")]
    assert _rows(REQ + "Bash or shell scripting experience.", pol.Q) == [(("language.shell",), "language", "required")]
    assert _rows(REQ + "Experience with Python or Go.", pol.Q) == \
        [(("language.go", "language.python"), None, "required")]


def test_option_g_recognises_cued_go_only():
    assert _ids(REQ + "Experience with Go.", pol.G) == ["language.go"]
    assert _ids(REQ + "Strong Go programming skills.", pol.G) == ["language.go"]
    assert _ids(REQ + "A go-getter attitude and willingness to go the extra mile.", pol.G) == []
    assert _ids(REQ + "Experience with Go, Docker, and Kubernetes.", pol.G) == \
        ["infra.docker", "infra.kubernetes", "language.go"]


def test_g17_alternative_rows_are_untouched_except_go_recognition_on_g16_018():
    g16 = json.loads((ROOT / "evaluation/m11g16/compound_logic_controls.json").read_text(encoding="utf-8"))["controls"]

    def alt_rows(text, p):
        return [r for r in _rows(text, p) if len(r[0]) > 1 or r[1] == "alternative_requirement"]
    for p in (pol.A, pol.B, pol.C, pol.Q, pol.D, pol.DB, *ph.POSTHOC):
        assert all(alt_rows(c["text"], pol.BASE) == alt_rows(c["text"], p) for c in g16), p.name
    changed = [c["id"] for c in g16 if alt_rows(c["text"], pol.BASE) != alt_rows(c["text"], pol.G)]
    assert changed == ["m11g16-018"]
    assert _rows(next(c["text"] for c in g16 if c["id"] == "m11g16-018"), pol.G) == \
        [((), "alternative_requirement", "required")]


# ---- M10E-g3 ---------------------------------------------------------------------------------------
def test_m10e_g3_frozen_gold_and_the_two_measured_dimensions():
    corpus = json.loads((ROOT / "evaluation/m10e/narrative_controls.json").read_text(encoding="utf-8"))
    g3 = next(c for c in corpus["controls"] if c["id"] == "m10e-g3")
    assert g3["text"] == "You will learn SQL, but prior knowledge of databases is required."
    assert g3["should_create_job_requirement"] is True
    assert g3["technical_concepts_may_enter_scoring"] is False
    assert "SQL" not in g3["purpose_rationale"]  # no frozen gold field names a SQL requirement
    doc = f"{g3['section_context']}\n{g3['text']}"
    if V14:  # row-existence projection passes; the concept-scoring field is violated by the SQL row
        assert _rows(doc) == [(("language.sql",), "language", "required")]
    for p in (pol.A, pol.B, pol.C, pol.Q, pol.D, pol.DB, *ph.POSTHOC):
        assert _rows(doc, p) == _rows(doc), p.name  # no G22 candidate touches g3
    assert _rows(doc, pol.E) == []  # clause scoping alone would break the row-existence gold


# ---- report reproducibility / publication safety ---------------------------------------------------
@only_v14
def test_public_report_is_reproducible_byte_identically():
    import evaluate_m11g22_concept_precision as runner
    # G14 canonical contract: a core.autocrlf=true checkout holds the committed report with CRLF line endings
    committed = gi.canonical_bytes((DATA / "concept_precision_report.json").read_bytes())
    assert runner.encode(runner.build_report()) == committed


def test_private_aggregates_are_integer_counts_only():
    path = DATA / "private_concept_aggregates.json"
    agg = json.loads(path.read_text(encoding="utf-8"))
    assert set(agg["note"].split()) >= {"integer", "counts", "only"}

    def walk(obj):
        if isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)
        else:
            assert isinstance(obj, int), obj
    walk({k: v for k, v in agg.items() if k != "note"})


def test_production_is_unchanged_and_never_imports_the_research_adapters():
    assert JOB_DESCRIPTION_PARSER_VERSION == "job_description_parser:v14"
    assert SCORING_VERSION == "github_evidence_alignment:v2"
    for py in (ROOT / "src").rglob("*.py"):
        assert "m11g22" not in py.read_text(encoding="utf-8"), py
    assert all(not is_unresolved_concept_id(c.concept_id) for c in default_registry().all_concepts())
