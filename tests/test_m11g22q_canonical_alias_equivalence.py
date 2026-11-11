"""Milestone 11-G22-Q -- canonical alias-equivalence correction (parser v15).

An OR whose alternatives are only different registry aliases of ONE canonical concept
("Kubernetes or k8s", "Go or Golang") is not a choice between technologies. Parser v14
classified it as an unsafe alternative and emitted a non-assessable
`alternative_requirement` placeholder; v15 routes it to the ordinary single-concept
path, so it becomes one `concept_id` requirement.

Written BEFORE the production change (red on v14 for every test that asserts the
correction; the preservation tests are green on both versions). Expected v14 values
used as "unchanged" references were taken from the live v14 parser at fad7c6d.

Revised once during implementation: the first rule (every alternative's segment
resolves to the same id) merged G13-o012 "Docker or Docker Compose" (gold: related,
NON-equivalent) through the embedded "Docker" mention. The rule now also requires
each alternative to be a WHOLE registry alias; the o012, "Strong knowledge of ...",
"(preferred)" and G22-e25 "shell scripting" cases were moved to the not-established
side accordingly (all keep their v14 placeholder).
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

from gitscore.assessment import SCORING_VERSION, assess_job  # noqa: E402
from gitscore.concepts.registry import default_registry  # noqa: E402
from gitscore.jobs.parsing import alternatives as alt  # noqa: E402
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION, parse_job_description_with_diagnostics  # noqa: E402
from gitscore.jobs.parsing.segmentation import segment_description  # noqa: E402
from gitscore.matching import match_job  # noqa: E402
from m11g15_or_scoring import candidate_profile  # noqa: E402

REQ = "Requirements:\n- "
K8S = ("infra.kubernetes",)
GO = ("language.go",)
PLACEHOLDER = ((), "alternative_requirement", "required")


def _rows(text: str) -> list[tuple]:
    return [(tuple(sorted(r.alternative_concept_ids)) or ((r.concept_id,) if r.concept_id else ()), r.category,
             r.necessity.value) for r in parse_job_description_with_diagnostics(text).profile.requirements]


def _assess(text: str, evidence: list[str]):
    return assess_job(match_job(candidate_profile(evidence), parse_job_description_with_diagnostics(text).profile))


def _only_match(text: str, evidence: list[str]):
    a = _assess(text, evidence)
    (m,) = a.match_analysis.requirement_matches
    return a, m


# ---- versions ---------------------------------------------------------------------------------------
def test_versions():
    assert JOB_DESCRIPTION_PARSER_VERSION == "job_description_parser:v15"
    assert SCORING_VERSION == "github_evidence_alignment:v2"


# ---- 1. Kubernetes or k8s ---------------------------------------------------------------------------
@pytest.mark.parametrize("text", [
    REQ + "Experience with Kubernetes or k8s is required.",   # G15-I1 wording
    REQ + "Experience with K8s or Kubernetes.",               # G22 e21
    REQ + "kubernetes or K8S.",                               # capitalisation
    REQ + "Kubernetes or k8s.",                               # bare list item
    "Kubernetes or k8s experience.",                          # no heading, trailing filler
])
def test_kubernetes_or_k8s_is_one_kubernetes_requirement(text):
    assert _rows(text) == [(K8S, "infrastructure", "required")]
    assert alt.equivalent_alias_concept_id(text.split("\n- ")[-1]) == "infra.kubernetes"


# ---- 2. Go or Golang (both already resolved by the existing resolver) -------------------------------
@pytest.mark.parametrize("text", [
    REQ + "Experience with Go or Golang",      # G18-16
    REQ + "Experience with Go or Golang.",     # G22 d19
    REQ + "Golang or Go experience.",          # G22 e17
    REQ + "Experience with go or golang.",     # lowercase: isolated OR-segment "go" already resolves in v14 (M6B.1)
])
def test_go_or_golang_is_one_go_requirement(text):
    assert _rows(text) == [(GO, "language", "required")]


def test_go_without_a_registry_resolution_is_not_assumed():
    # prose "go" never resolves; the equivalence path is not a new Go recogniser (Option G not implemented)
    assert _rows(REQ + "Must be able to go or travel to client sites.") == [((), "unresolved_requirement", "required")]
    assert alt.equivalent_alias_concept_id("Must be able to go or travel to client sites.") is None
    # an alternative carrying descriptive prose is not a bare alias -> conservative placeholder (unchanged from v14)
    assert _rows(REQ + "Golang or Go for backend services.") == [PLACEHOLDER]


# ---- 3. single technology, no OR: unchanged --------------------------------------------------------
def test_single_technology_without_or_is_unchanged():
    assert _rows(REQ + "Experience with Kubernetes.") == [(K8S, "infrastructure", "required")]
    assert _rows(REQ + "Experience with Go.") == [((), "unresolved_requirement", "required")]
    assert alt.equivalent_alias_concept_id("Experience with Kubernetes.") is None


# ---- 4. genuine OR of different technologies --------------------------------------------------------
@pytest.mark.parametrize("text,members", [
    ("Experience with Python or Go.", ("language.go", "language.python")),
    ("Experience with Docker or Kubernetes.", ("infra.docker", "infra.kubernetes")),
    ("Experience with Kubernetes or Nomad.", ("infra.kubernetes", "unresolved:nomad")),
])
def test_genuine_alternatives_remain_one_or_group(text, members):
    assert _rows(REQ + text) == [(members, None, "required")]
    assert alt.classify_alternative_claim(text).kind == "technical"
    assert alt.equivalent_alias_concept_id(text) is None


# ---- 5 / 6. repeated alias and three aliases ---------------------------------------------------------
@pytest.mark.parametrize("text", [
    REQ + "Kubernetes or Kubernetes.",
    REQ + "Kubernetes, K8s, or k8s",
    REQ + "Experience with Kubernetes, K8s, or k8s.",
])
def test_repeated_or_three_aliases_collapse_to_one_requirement(text):
    assert _rows(text) == [(K8S, "infrastructure", "required")]


# ---- 7. two equivalent aliases plus a different concept ---------------------------------------------
@pytest.mark.parametrize("text,members", [
    ("Experience with Kubernetes or k8s or Docker.", ("infra.docker", "infra.kubernetes")),
    ("Experience with K8s, Kubernetes, or OpenShift.", ("infra.kubernetes", "unresolved:openshift")),
])
def test_equivalent_aliases_beside_a_different_concept_keep_the_different_alternative(text, members):
    assert _rows(REQ + text) == [(members, None, "required")]  # v14 already deduplicated these; unchanged
    assert alt.equivalent_alias_concept_id(text) is None


# ---- 8 / 17. unknown or ambiguous alternatives are not assumed equivalent ---------------------------
@pytest.mark.parametrize("text", [
    "Experience with Kubernetes or a similar orchestrator.",       # unknown alternative
    "You should react calmly under pressure or use React daily.",  # verb "react" is a false identity (G22 class A)
    "Experience with React or react quickly to incidents.",
    "3+ years of experience with Kubernetes or k8s.",              # first alternative is prose, not a bare alias
    "Experience with at least one of Kubernetes or k8s.",
    "Strong knowledge of Kubernetes or k8s.",                      # cleaned term "knowledge of Kubernetes" is no alias
    "Experience with Docker or Docker Compose.",                   # G13-o012: embedded alias, different tool
    "Bash or shell scripting experience.",                         # G22-e25: "shell scripting" is no registry alias
])
def test_unestablished_equivalence_keeps_the_non_assessable_placeholder(text):
    assert alt.equivalent_alias_concept_id(text) is None
    assert _rows(REQ + text) == [PLACEHOLDER]
    a, m = _only_match(REQ + text, ["infra.kubernetes", "framework.react"])
    assert m.status.value == "not_assessable"
    assert not a.counts_toward_alignment(m) and a.assessable_count == 0 and a.alignment_score is None


# ---- 9. mixed AND/OR stays contained by G17 ---------------------------------------------------------
@pytest.mark.parametrize("text", [
    "Experience with Python and Kubernetes or k8s.",
    "At least two of Kubernetes, k8s, or Docker.",
    "Kubernetes or k8s, and Python.",
    "Experience with both Kubernetes or k8s.",
    "Experience with Kubernetes or k8s, and Docker or Podman.",
])
def test_mixed_and_or_remains_conservatively_contained(text):
    assert _rows(REQ + text) == [PLACEHOLDER]
    assert alt.classify_alternative_claim(text).kind == "unsafe"
    assert alt.equivalent_alias_concept_id(text) is None


def test_g17_structural_signal_wins_over_equivalence():
    text = "Experience with both Kubernetes or k8s."
    assert alt.is_structurally_mixed(text)
    assert alt.equivalent_alias_concept_id(text) is None


# ---- 10. related concepts are not equivalent --------------------------------------------------------
@pytest.mark.parametrize("text,members", [
    ("Experience with PostgreSQL or SQL.", ("database.postgresql", "language.sql")),
    ("Experience with React or Next.js.", ("framework.nextjs", "framework.react")),
    ("Experience with JavaScript or TypeScript.", ("language.javascript", "language.typescript")),
    ("Experience with PyTorch or TensorFlow.", ("ml.framework.pytorch", "ml.framework.tensorflow")),
    ("Experience with FreeRTOS or RTOS.", ("embedded.rtos.freertos", "unresolved:rtos")),  # parent edge only
])
def test_related_or_parent_child_concepts_are_never_equated(text, members):
    assert _rows(REQ + text) == [(members, None, "required")]
    assert alt.equivalent_alias_concept_id(text) is None


def test_equivalence_uses_the_registry_identity_only():
    registry = default_registry()
    assert registry.get("embedded.rtos.freertos").parent_id == "embedded.rtos"
    assert registry.get("embedded.rtos") is None  # the only parent edge has no registered parent to equate


# ---- 11. original text and source span ---------------------------------------------------------------
@pytest.mark.parametrize("text", [
    REQ + "Experience with Kubernetes or k8s is required.",
    "Nice to have:\n- Experience with Go or Golang.",
    REQ + "Kubernetes or k8s.\n- Experience with Python.",
])
def test_original_text_and_source_span_are_the_claim(text):
    claims = segment_description(text)
    rows = parse_job_description_with_diagnostics(text).profile.requirements
    for r in rows:
        assert text[r.source_span.start:r.source_span.end] == r.original_text
        assert any((c.start, c.end, c.text) == (r.source_span.start, r.source_span.end, r.original_text)
                   for c in claims)


def test_neighbouring_bullets_are_unaffected():
    assert _rows(REQ + "Kubernetes or k8s.\n- Experience with Python.") == \
        [(K8S, "infrastructure", "required"), (("language.python",), "language", "required")]


# ---- 12. necessity preserved -------------------------------------------------------------------------
@pytest.mark.parametrize("text,necessity", [
    (REQ + "Experience with Kubernetes or k8s is required.", "required"),
    ("Nice to have:\n- Kubernetes or k8s", "preferred"),
    ("Nice to have:\n- Experience with Go or Golang.", "preferred"),
    ("Preferred qualifications:\n- Experience with Postgres or PostgreSQL.", "preferred"),
])
def test_necessity_is_preserved(text, necessity):
    (row,) = _rows(text)
    assert row[0] in (K8S, GO, ("database.postgresql",)) and row[2] == necessity


def test_inline_necessity_marker_is_not_stripped_so_the_placeholder_and_its_necessity_remain():
    # "k8s (preferred)" is not a bare alias for the existing list-fragment cleaner -> v14 placeholder, PREFERRED kept
    assert _rows(REQ + "Experience with Kubernetes or k8s (preferred).") == \
        [((), "alternative_requirement", "preferred")]


@pytest.mark.parametrize("text,unparsed", [
    ("About us:\n- Kubernetes or k8s", 0),                                 # no necessity -> no row (unchanged)
    (REQ + "Experience with Kubernetes or k8s is not required.", 1),      # G21 negation -> UnparsedClaim
    ("Responsibilities:\n- Deploy services to Kubernetes or k8s.", 1),    # G21 admission declines duties
])
def test_unknown_necessity_and_g21_admission_are_unchanged(text, unparsed):
    parsed = parse_job_description_with_diagnostics(text)
    assert parsed.profile.requirements == ()
    assert len(parsed.unparsed_claims) == unparsed


# ---- 13. G21 admission unchanged ---------------------------------------------------------------------
def test_g21_admission_is_identical_for_equivalent_and_single_concept_wording():
    for duty in ("Deploy services to Kubernetes or k8s.", "Deploy services to Kubernetes."):
        parsed = parse_job_description_with_diagnostics("Responsibilities:\n- " + duty)
        assert parsed.profile.requirements == () and len(parsed.unparsed_claims) == 1


# ---- 14 / 15 / 16. matcher, scoring v2, unrelated evidence ------------------------------------------
@pytest.mark.parametrize("text,concept", [
    (REQ + "Experience with Kubernetes or k8s is required.", "infra.kubernetes"),
    (REQ + "Experience with Go or Golang", "language.go"),
])
def test_matcher_and_scoring_v2_count_one_eligible_requirement(text, concept):
    a, m = _only_match(text, [concept])
    assert m.requirement.concept_id == concept and m.status.value == "supported"
    assert a.counts_toward_alignment(m) and a.assessable_count == 1 and a.alignment_score == 100
    a, m = _only_match(text, [])
    assert m.status.value == "not_observed"
    assert a.counts_toward_alignment(m) and a.assessable_count == 1 and a.alignment_score == 0


@pytest.mark.parametrize("text,unrelated", [
    (REQ + "Experience with Kubernetes or k8s is required.", ["infra.docker", "language.go", "cloud.aws"]),
    (REQ + "Experience with Go or Golang", ["infra.kubernetes", "language.python", "language.javascript"]),
])
def test_unrelated_positive_evidence_never_satisfies_the_requirement(text, unrelated):
    a, m = _only_match(text, unrelated)
    assert m.status.value == "not_observed" and a.alignment_score == 0


# ---- frozen historical gold: G15-I1, G18-16, G22 equivalence controls -------------------------------
def _control(rel: str, cid: str) -> dict:
    return next(c for c in json.loads((ROOT / rel).read_text(encoding="utf-8"))["controls"] if c["id"] == cid)


def test_g15_i1_matches_its_frozen_alias_gold():
    c = _control("evaluation/m11g15/or_scoring_controls.json", "m11g15-I1")
    (g,) = c["gold_requirements"]
    assert g["structure"] == "alias" and [m["concept_id"] for m in g["members"]] == list(K8S)
    assert _rows(c["job_text"]) == [(K8S, "infrastructure", g["necessity"])]
    for cand in c["candidates"]:
        _, m = _only_match(c["job_text"], cand["evidence"])
        assert m.status.value.upper() == c["expected"][cand["name"]]["g1"]["closest_public_status"]


def test_g18_16_matches_its_frozen_expected_scores():
    c = _control("evaluation/m11g18/eligibility_controls.json", "m11g18-16")
    (g,) = c["gold_requirements"]
    assert g["structure"] == "alias" and [m["concept_id"] for m in g["members"]] == list(GO)
    assert _rows(c["job_text"]) == [(GO, "language", g["necessity"])]
    for cand in c["candidates"]:
        a = _assess(c["job_text"], cand["evidence"])
        exp = c["expected_scores"][cand["name"]]["declared"]
        supported = sum(1 for m in a.match_analysis.requirement_matches
                        if a.counts_toward_alignment(m) and m.status.value == "supported")
        assert (supported, a.assessable_count, a.alignment_score) == (exp["supported"], exp["eligible"], exp["score"])


@pytest.mark.parametrize("split,cid", [("dev", "m11g22-d19"), ("eval", "m11g22-e17"), ("eval", "m11g22-e20"),
                                       ("eval", "m11g22-e21")])
def test_g22_equivalent_alias_controls_reach_their_frozen_expectation(split, cid):
    c = _control(f"evaluation/m11g22/concept_controls_{split}.json", cid)
    assert c["family"] == "equivalent_alias"
    expected = [(tuple(e["members"]), e["necessity"]) for e in c["expected_concepts"]]
    assert [(r[0], r[2]) for r in _rows(c["text"])] == expected


def test_g22_e25_is_not_recovered_because_shell_scripting_is_not_a_registry_alias():
    # Divergence from the G22 Q SIMULATION (which accepted the embedded "shell" mention): production v15 requires
    # every alternative to be a whole registry alias, the rule that keeps "Docker or Docker Compose" an OR.
    c = _control("evaluation/m11g22/concept_controls_eval.json", "m11g22-e25")
    assert c["expected_concepts"] == [{"members": ["language.shell"], "necessity": "required"}]  # frozen, unchanged
    assert _rows(c["text"]) == [PLACEHOLDER]  # v14 placeholder retained (no regression, no recovery)


def test_g13_o012_related_non_equivalent_alternatives_stay_unmerged():
    c = _control("evaluation/m11g13/generalization_controls.json", "m11g13-o012")
    assert c["gold_structure"] == "or_any"
    assert alt.equivalent_alias_concept_id(c["job_text"]) is None
    assert _rows(c["job_text"]) == [PLACEHOLDER]


def test_g13_o007_equivalent_aliases_match_their_gold():
    c = _control("evaluation/m11g13/generalization_controls.json", "m11g13-o007")
    assert c["gold_structure"] == "equivalent_aliases" and c["gold_scored_requirement_count"] == 1
    assert _rows(c["job_text"]) == [(K8S, "infrastructure", c["gold_necessity"])]
    _, m = _only_match(c["job_text"], c["candidate_evidence_concepts"])
    assert (m.status.value == "supported") is c["gold_candidate_satisfies"]


# ---- 18. G16 residuals 018 / 043: no new false SUPPORTED --------------------------------------------
# (supported counted, assessable, score) per fixture -- measured on live v14 at fad7c6d, before this change.
_G16_V14 = {
    "m11g16-018": {"only_A": (1, 1, 100), "only_B": (0, 1, 0), "only_C": (1, 1, 100), "only_D": (1, 1, 100),
                   "A_and_C": (1, 1, 100), "B_and_C": (1, 1, 100), "all_members": (1, 1, 100), "none": (0, 1, 0),
                   "irrelevant": (0, 1, 0)},
    "m11g16-043": {"only_A": (1, 1, 100), "only_B": (1, 1, 100), "only_C": (1, 1, 100), "A_and_C": (1, 1, 100),
                   "B_and_C": (1, 1, 100), "all_members": (1, 1, 100), "none": (0, 1, 0), "irrelevant": (0, 1, 0)},
}


@pytest.mark.parametrize("cid", sorted(_G16_V14))
def test_g16_residuals_018_and_043_are_unchanged(cid):
    c = _control("evaluation/m11g16/compound_logic_controls.json", cid)
    assert alt.equivalent_alias_concept_id(c["text"]) is None
    for fx, f in c["expected"]["per_fixture"].items():
        a = _assess(c["text"], f["evidence"])
        supported = sum(1 for m in a.match_analysis.requirement_matches
                        if a.counts_toward_alignment(m) and m.status.value == "supported")
        assert (supported, a.assessable_count, a.alignment_score) == _G16_V14[cid][fx], fx


def test_no_g16_compound_control_is_treated_as_an_alias_equivalence():
    controls = json.loads((ROOT / "evaluation/m11g16/compound_logic_controls.json").read_text(encoding="utf-8"))
    assert all(alt.equivalent_alias_concept_id(c["text"]) is None for c in controls["controls"])


# ---- classifier contract ----------------------------------------------------------------------------
def test_classifier_routes_only_an_established_equivalence_to_the_single_concept_path():
    assert alt.classify_alternative_claim("Experience with Kubernetes or k8s is required.").kind == "not_technical"
    assert alt.classify_alternative_claim("Experience with Kubernetes or a similar orchestrator.").kind == "unsafe"
    assert alt.classify_alternative_claim("Experience with Python or Go.") == \
        alt.AlternativeClaim(kind="technical", concept_ids=("language.go", "language.python"))


# ---- committed real v14-vs-v15 comparison (scripts/evaluate_m11g22q_v14_v15.py) ----------------------
_CMP = ROOT / "evaluation" / "m11g22q"
_V14_REF = "fad7c6dc3dd8608e382478ed10156b414d86b7ae"


def _comparison() -> dict:
    return json.loads((_CMP / "v14_v15_comparison.json").read_text(encoding="utf-8"))


def test_comparison_is_pinned_to_the_g22_commit_and_ran_on_identical_inputs():
    import evaluate_m11g22q_v14_v15 as cmp_runner
    assert cmp_runner.V14_REF == _V14_REF  # a fixed commit, never a moving HEAD reference
    c = _comparison()
    assert c["versions"]["v14"] == ["job_description_parser:v14", "github_evidence_alignment:v2",
                                    "requirement_matcher:v1", _V14_REF]
    assert c["versions"]["v15"][:3] == ["job_description_parser:v15", "github_evidence_alignment:v2",
                                        "requirement_matcher:v1"]
    p = c["pins"]
    assert p["clone_head"] == _V14_REF and p["v14_src_identical_to_g21_commit"] is True
    assert p["tracked_inputs"]["identical_modulo_newlines"] is True and p["tracked_inputs"]["txt_byte_identical"]
    assert p["g22_committed_report_reproduced_by_pinned_v14"] is True
    assert c["production_files_changed"] == ["src/gitscore/jobs/parsing/alternatives.py",
                                             "src/gitscore/jobs/parsing/parser.py"]


def test_comparison_recovers_only_alias_equivalences_and_preserves_every_or_group():
    ae = _comparison()["alias_equivalence"]
    assert ae["recovered"] == [["corpus:g15", "m11g15-I1", ["infra.kubernetes"], "required"],
                               ["corpus:g18", "m11g18-16", ["language.go"], "required"],
                               ["g13_or_contract", "m11g13-o007", ["infra.kubernetes"], "required"]]
    assert ae["genuine_or_groups_preserved_v15"] == ae["genuine_or_groups_v14"] > 0
    assert ae["other_row_or_unparsed_changes"] == []


def test_comparison_shows_no_false_supported_and_no_other_score_change():
    c = _comparison()
    assert c["new_supported_rows"] == {
        "new_true_supported": ["g15:m11g15-I1/k8s_evidence:infra.kubernetes", "g18:m11g18-16/go:language.go"],
        "new_false_supported": [], "new_supported_without_frozen_truth": []}
    assert c["match_status"]["transitions"] == {"not_assessable -> not_observed+counted": 2,
                                                "not_assessable -> supported+counted": 2}
    s = c["g22_fixture_scoring"]
    assert s["g16"]["g16_claim_false_supported"] == [7, 7]
    for name in ("g16", "8c_v1", "8c_v1_1", "m10"):
        assert (s[name]["score_changed"], s[name]["denominator_changed"], s[name]["became_undefined"],
                s[name]["status_changed"], s[name]["evidence_changed"]) == ([], [], [], [], []), name
    assert s["g15"]["became_defined"] == ["m11g15-I1/k8s_evidence", "m11g15-I1/neither"]
    assert s["g15"]["score_changed"] == [["m11g15-I1/k8s_evidence", None, 100], ["m11g15-I1/neither", None, 0]]
    assert s["g18"]["became_defined"] == ["m11g18-16/go", "m11g18-16/none"]
    assert s["g18"]["score_changed"] == [["m11g18-16/go", None, 100], ["m11g18-16/none", None, 0]]
    for name in ("g15", "g18"):
        assert s[name]["became_undefined"] == [] and s[name]["supported_counted_delta"] == 1, name
    assert c["g17_guard"]["violations"] == []


def test_comparison_g22_controls_and_m10e_g3():
    c = _comparison()
    assert sorted(c["g22_controls"]["dev"]["changed_controls"]) == ["m11g22-d19"]
    assert sorted(c["g22_controls"]["eval"]["changed_controls"]) == ["m11g22-e17", "m11g22-e20", "m11g22-e21"]
    for split in ("dev", "eval"):
        a, b = c["g22_controls"][split]["v14"], c["g22_controls"][split]["v15"]
        assert (a["false_registered"], a["fabricated_unresolved"], a["false_supported_counted"]) == \
            (b["false_registered"], b["fabricated_unresolved"], b["false_supported_counted"])  # G22 residuals remain
    g3 = c["m10e"]["g3_live"]
    assert g3["v14"] == g3["v15"] and g3["v15"]["technical_concept_counted"] is True  # out of scope, still open
    assert c["m10e"]["g3_frozen_gold"]["technical_concepts_may_enter_scoring"] is False


def test_private_comparison_is_integer_counts_only_and_unchanged():
    agg = json.loads((_CMP / "private_v14_v15_aggregates.json").read_text(encoding="utf-8"))
    assert set(agg["note"].split()) >= {"integer", "counts", "only"}

    def walk(obj):
        if isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)
        else:
            assert isinstance(obj, int) and not isinstance(obj, bool), obj
    walk({k: v for k, v in agg.items() if k != "note"})
    assert sum(v["postings"] for v in agg["concept_view"].values()) == 62
    assert all(v["postings_changed"] == 0 for v in agg["concept_view"].values())
