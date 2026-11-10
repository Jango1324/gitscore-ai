"""Milestone 11-G21 -- qualification-intent admission guard (B1NR) + necessity refinement.

Production port of G20's evaluated policy B1NR. Every expectation here was written
from G20's gold labels / the milestone brief, never from v14 output. Run against the
REAL production parser (and, where noted, matcher + scoring v2 + API serializer).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "scripts", REPO_ROOT / "scripts" / "evaluation_lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from gitscore.api.serialization import serialize_job_analysis_result  # noqa: E402
from gitscore.application import JobAnalysisResult  # noqa: E402
from gitscore.assessment import SCORING_VERSION, assess_job  # noqa: E402
from gitscore.jobs.parsing import qualification_intent as qi  # noqa: E402
from gitscore.jobs.parsing.necessity import refine_necessity  # noqa: E402
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION, parse_job_description_with_diagnostics  # noqa: E402
from gitscore.jobs.types import Necessity  # noqa: E402
from gitscore.matching import match_job  # noqa: E402

R, P = "required", "preferred"


def parse(text: str):
    return parse_job_description_with_diagnostics(text)


def rows(text: str) -> list[tuple]:
    """(members, category, necessity) per JobRequirement."""
    out = []
    for r in parse(text).profile.requirements:
        members = tuple(sorted(r.alternative_concept_ids)) or ((r.concept_id,) if r.concept_id else ())
        out.append((members, r.category, r.necessity.value))
    return out


def concepts(text: str) -> dict[str, str]:
    """concept id -> necessity for every technical member."""
    return {m: n for ms, _, n in rows(text) for m in ms}


def unparsed(text: str) -> list[str]:
    return [u.text for u in parse(text).unparsed_claims]


# ---- versions --------------------------------------------------------------------------------------
def test_parser_v14_and_scoring_v2():
    assert JOB_DESCRIPTION_PARSER_VERSION == "job_description_parser:v14"
    assert SCORING_VERSION == "github_evidence_alignment:v2"


# ---- 1-5: qualification vs narrative / duty ---------------------------------------------------------
def test_01_explicit_required_qualification_is_admitted():
    assert concepts("Experience with Python is required.") == {"language.python": R}


def test_02_team_narrative_is_not_a_qualification():
    assert rows("Our team uses Python.") == []
    assert rows("We use Kafka, Python and Snowflake to power analytics for retailers.") == []
    assert rows("Our mobile app is written in Swift and Kotlin and serves two million riders.") == []


def test_03_you_must_have_is_a_qualification():
    assert concepts("You must have experience with Kubernetes.") == {"infra.kubernetes": R}


def test_04_on_call_duty_without_a_technology_yields_no_requirement():
    text = "You must be on call during weekends."
    assert rows(text) == []  # no JobRequirement in v13 or v14 (no signal: never even a claim)


def test_04b_known_limitation_on_call_duty_naming_a_technology_is_still_admitted():
    """G20 held-out h003, explicitly characterized (NOT xfailed, NOT hidden): B1NR treats
    'you must' as a strong candidate frame, the same shape as 'you must have', so a duty
    sentence that also names a technology is still admitted as REQUIRED. If a future
    milestone fixes this, this test must be updated deliberately."""
    assert concepts("You must be on call one week per month for our AWS infrastructure.") == {"cloud.aws": R}


def test_05_obligation_inside_a_duty_does_not_establish_qualification():
    assert rows("You will be required to deploy services.") == []
    text = "You will be required to deploy services to AWS and Kubernetes."
    assert rows(text) == []
    assert unparsed(text) == [text]
    assert rows("What you'll do:\n- You will be required to deploy services to AWS and Kubernetes.") == []


# ---- 6-10: genuine qualifications preserved ----------------------------------------------------------
def test_06_required_qualification_under_unconventional_heading():
    assert concepts("Must-haves:\n- Experience with FastAPI.\n- Experience with PostgreSQL.") == {
        "framework.fastapi": R, "database.postgresql": R}


def test_06b_candidate_profile_headings_unchanged_until_g23():
    """G21 must NOT change heading policy: 'About you' still suppresses (G6/G23 scope)."""
    assert rows("About you:\n- 4+ years of experience with Java.") == []


def test_07_preferred_qualifications():
    assert concepts("Nice-to-haves:\n- Experience with Redis.") == {"database.redis": P}
    assert concepts("Knowledge of Docker is a plus.") == {"infra.docker": P}
    assert concepts("Familiarity with PyTorch or TensorFlow is preferred.") == {
        "ml.framework.pytorch": P, "ml.framework.tensorflow": P}


def test_08_bare_technical_list_under_qualification_heading():
    assert rows("Requirements:\n- Java, Python and/or Go") == [
        (("language.go", "language.java", "language.python"), None, R)]


def test_08b_bare_unsectioned_lists_are_not_declined_for_lacking_intent():
    """The rejected G20 'require intent' variant destroyed these (M10D)."""
    assert rows("Java, Python and/or Go")
    assert rows("Python or Java and SQL")


def test_09_prose_qualifications():
    text = ("We're hiring a backend developer. You should have solid experience with Golang and Redis. "
            "Knowledge of Kubernetes is a plus.")
    assert concepts(text) == {"language.go": R, "database.redis": R, "infra.kubernetes": P}


def test_10_lists_inherit_section_necessity():
    text = "Required skills:\n- Python\n- SQL\n- Docker\n\nPreferred skills:\n- Kubernetes\n- AWS"
    assert concepts(text) == {"language.python": R, "language.sql": R, "infra.docker": R,
                              "infra.kubernetes": P, "cloud.aws": P}


# ---- 11-13: narrative / duty inside qualification sections, tech discussion ---------------------------
def test_11_narrative_inside_a_qualification_section():
    text = "Qualifications:\n- Experience with Docker.\n- Our team has grown to 40 engineers across Python and Golang services."
    assert concepts(text) == {"infra.docker": R}


def test_12_responsibilities_under_a_misleading_requirements_heading():
    text = "Role requirements:\n- Design and ship APIs in Golang.\n- Own the on-call rotation for our Redis clusters."
    assert rows(text) == []
    assert len(unparsed(text)) == 2


def test_12b_mixed_duty_and_qualification_bullet_is_kept():
    assert concepts("Key Requirements:\n- Lead the migration from Java to Kotlin.\n- Expert knowledge of Kotlin.") == {
        "language.kotlin": R}
    assert concepts("Responsibilities:\n- Maintain our Python services; strong Python experience is required.") == {
        "language.python": R}


def test_13_generic_technology_discussion():
    assert rows("Kubernetes adoption has grown rapidly across the industry.") == []
    assert rows("Rust is gaining popularity for systems programming.") == []
    assert rows("Requirements:\n- Experience with React.\n- React remains the most popular frontend library.") == [
        (("framework.react",), "frontend_framework", R)]


# ---- 14-15: G17-053, G18-25 ---------------------------------------------------------------------------
def _frozen(rel, cid, key):
    return next(c for c in json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))["controls"] if c["id"] == cid)[key]


def test_14_g17_053_responsibility_is_declined_not_a_required_placeholder():
    text = _frozen("evaluation/m11g16/compound_logic_controls.json", "m11g16-053", "text")
    assert rows(text) == []
    assert unparsed(text) == [text]


def test_15_g18_25_company_narrative_produces_no_requirement_and_an_undefined_score():
    from m11g15_or_scoring import candidate_profile

    text = _frozen("evaluation/m11g18/eligibility_controls.json", "m11g18-25", "job_text")
    parsed = parse(text)
    assert parsed.profile.requirements == ()
    a = assess_job(match_job(candidate_profile(["language.python", "infra.docker"]), parsed.profile))
    assert a.alignment_score is None and a.assessable_count == 0


# ---- 16: the two G20 post-hoc defects ------------------------------------------------------------------
def test_16a_us_country_abbreviation_is_not_the_employer_pronoun():
    assert not qi.frames("US work authorization is required.")["employer"]
    assert qi.frames("us engineers ship daily")["employer"]
    assert qi.frames("We use Python.")["employer"] and qi.frames("Our team uses Go.")["employer"]
    assert rows("US work authorization is required.") == [((), "legal", R)]
    assert rows("Requirements:\n- US work authorization is required.") == [((), "legal", R)]


def test_16b_concessive_negation_is_a_preference_not_a_negation():
    text = "Requirements:\n- Although not required, Rust experience is a plus."
    assert concepts(text) == {"language.rust": P}
    assert concepts("While not required, Golang experience is a plus.") == {"language.go": P}


# ---- 17: near-neighbour pairs (G20 frozen controls) -----------------------------------------------------
def _pairs():
    out = []
    for split in ("dev", "holdout"):
        doc = json.loads((REPO_ROOT / f"evaluation/m11g20/admission_controls_{split}.json").read_text(encoding="utf-8"))
        for c in doc["controls"]:
            if c["pair"]:
                out.append(pytest.param(c, id=c["id"]))
    return out


@pytest.mark.parametrize("control", _pairs())
def test_17_near_neighbour_members(control):
    (unit,) = control["units"]
    got = rows(control["text"])
    if unit["qual"]:
        got_concepts = {m for ms, _, _ in got for m in ms}
        assert set(unit["tech"]) <= got_concepts or (not unit["tech"] and got)
        assert {n for _, _, n in got} == {unit["nec"]}
    else:
        assert got == []


# ---- 18: independent requirements in mixed-content postings ---------------------------------------------
def test_18_independent_requirements_survive_mixed_content():
    text = ("We are a logistics startup in Montreal. Candidates must have strong experience with Python and "
            "PostgreSQL. We offer flexible hours and a learning budget.")
    assert concepts(text) == {"language.python": R, "database.postgresql": R}
    text = ("Responsibilities:\n- Design data pipelines in Python and SQL.\n- Maintain our PostgreSQL clusters.\n\n"
            "Requirements:\n- 3+ years of experience with Python.\n- Strong SQL skills.")
    assert concepts(text) == {"language.python": R, "language.sql": R}


def test_18b_section_leak_paragraph_is_not_a_requirement():
    text = "Requirements:\n- Experience with AWS.\n\nWe are a remote-first team that ships with Docker and Kubernetes every day."
    assert concepts(text) == {"cloud.aws": R}


# ---- 19-20: spans and diagnostics ------------------------------------------------------------------------
SPAN_TEXTS = [
    "Qualifications:\n- Experience with Docker.\n- Our team has grown to 40 engineers across Python and Golang services.",
    "We're hiring a backend developer. You should have solid experience with Golang and Redis. "
    "Knowledge of Kubernetes is a plus.",
    "Requirements:\n- Experience building data pipelines with\n  Python and PostgreSQL.\n- Familiarity with Docker.",
    "Role requirements:\n- Design and ship APIs in Golang.\n- Own the on-call rotation for our Redis clusters.",
]


@pytest.mark.parametrize("text", SPAN_TEXTS)
def test_19_exact_source_text_and_spans(text):
    parsed = parse(text)
    for r in parsed.profile.requirements:
        assert text[r.source_span.start:r.source_span.end] == r.original_text
    for u in parsed.unparsed_claims:
        assert text[u.source_span.start:u.source_span.end] == u.text


def test_20_declined_claims_stay_visible_as_diagnostics_in_the_api():
    from m11g15_or_scoring import candidate_profile

    text = "Qualifications:\n- Experience with Docker.\n- Our team has grown to 40 engineers across Python and Golang services."
    parsed = parse(text)
    declined = "Our team has grown to 40 engineers across Python and Golang services."
    assert declined in [u.text for u in parsed.unparsed_claims]
    profile = candidate_profile(["infra.docker"])
    resp = serialize_job_analysis_result(JobAnalysisResult(
        candidate_profile=profile, job_profile=parsed.profile, assessment=assess_job(match_job(profile, parsed.profile)),
        extractor_failures=(), unknown_dependency_names=(), unparsed_claims=parsed.unparsed_claims))
    assert declined in [u.text for u in resp.unparsed_claims]
    assert resp.assessment.unparsed_claim_count == len(resp.unparsed_claims)
    assert resp.assessment.github_evidence_alignment == 100 and resp.assessment.assessable_requirement_count == 1


# ---- necessity refinement (separately testable) ----------------------------------------------------------
@pytest.mark.parametrize("text,before,after", [
    ("Experience with Python is required.", Necessity.REQUIRED, Necessity.REQUIRED),
    ("Knowledge of Docker is a plus.", Necessity.PREFERRED, Necessity.PREFERRED),
    ("Experience with Python.", None, None),
    ("Experience with Python.", Necessity.REQUIRED, Necessity.REQUIRED),
    ("Experience with Python.", Necessity.PREFERRED, Necessity.PREFERRED),
    ("Familiarity with Rust would be great.", Necessity.REQUIRED, Necessity.PREFERRED),
    ("Knowledge of Redis is beneficial.", Necessity.REQUIRED, Necessity.PREFERRED),
    ("Exposure to CUDA is helpful but not essential.", Necessity.REQUIRED, Necessity.PREFERRED),
    ("Experience with Redis is not required, but appreciated.", Necessity.REQUIRED, Necessity.PREFERRED),
    ("Prior experience with Rust is not required.", Necessity.REQUIRED, None),
    ("While not required, Spark experience is a plus.", Necessity.REQUIRED, Necessity.PREFERRED),
    ("Python is required; Docker or Kubernetes is preferred.", Necessity.REQUIRED, Necessity.REQUIRED),
    ("Python is required, but Rust is not required.", Necessity.REQUIRED, Necessity.REQUIRED),
])
def test_refine_necessity(text, before, after):
    assert refine_necessity(text, before) is after


def test_refine_never_promotes():
    for text in ("Experience with Python is required.", "Must have Rust.", "Docker is essential."):
        assert refine_necessity(text, None) is None
        assert refine_necessity(text, Necessity.PREFERRED) is not Necessity.REQUIRED


def test_necessity_refinement_through_the_parser():
    assert concepts("Requirements:\n- Familiarity with Rust would be great.") == {"language.rust": P}
    assert concepts("Requirements:\n- Exposure to CUDA is helpful but not essential.") == {"platform.cuda": P}
    assert concepts("Requirements:\n- Experience with Redis is not required, but appreciated.") == {"database.redis": P}
    assert rows("No prior experience with Kubernetes is necessary.") == []
    assert rows("Prior experience with Rust is not required.") == []


# ---- module hygiene ----------------------------------------------------------------------------------------
def test_responsibility_lead_is_pinned_to_the_shadow_pattern():
    from gitscore.jobs.parsing.competency_extraction import _RESPONSIBILITY_LEAD

    assert qi.RESPONSIBILITY_LEAD.pattern == _RESPONSIBILITY_LEAD.pattern
    assert qi.RESPONSIBILITY_LEAD.flags == _RESPONSIBILITY_LEAD.flags


def test_decision_is_candidate_independent_and_pure():
    import inspect

    assert list(inspect.signature(qi.decide_qualification_intent).parameters) == ["text", "section_kind"]
    imports = [line for line in inspect.getsource(qi).splitlines() if line.startswith(("import ", "from "))]
    assert all(line.startswith(("from __future__", "import re", "from dataclasses", "from gitscore.jobs.parsing."))
               for line in imports), imports


def test_no_broad_content_blacklist():
    """Every frame is a grammatical shape; a strong candidate frame overrides any of them."""
    for text in ("We require 5+ years of experience with Java.", "Our ideal candidate knows Python.",
                 "We are looking for engineers with Rust experience.", "You will need experience with Go and Golang."):
        assert qi.decide_qualification_intent(text, None).admit, text
    assert not re.search(r"\b(?:python|docker|kubernetes|aws)\b", qi.EMPLOYER_SUBJECT.pattern, re.IGNORECASE)


# ---- v13 vs v14 comparison (committed output) and fresh adversarial set ------------------------------
G21 = REPO_ROOT / "evaluation" / "m11g21"


@pytest.fixture(scope="module")
def original() -> dict:
    """ORIGINAL v14 (pre negation-scope correction) comparison -- preserved, never regenerated."""
    return json.loads((G21 / "v13_v14_comparison.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def comparison() -> dict:
    """REVISED v14 (after the Option B negation-scope correction) -- the live implementation."""
    return json.loads((G21 / "v13_v14_revised_comparison.json").read_text(encoding="utf-8"))


def test_adversarial_freeze_verifies():
    import gold_integrity as gi

    res = gi.verify_frozen_file(G21 / "adversarial_controls.json", G21 / "adversarial_hash_freeze.json")
    assert res.method in ("raw", "canonical")
    doc = json.loads((G21 / "adversarial_controls.json").read_text(encoding="utf-8"))
    assert "NOT independent external validation" in doc["authorship_disclosure"]
    assert len(doc["controls"]) == 35


def test_comparison_pins_real_v13_and_v14(comparison):
    assert comparison["versions"]["v13"][:2] == ["job_description_parser:v13", "github_evidence_alignment:v2"]
    assert comparison["versions"]["v14"][:2] == ["job_description_parser:v14", "github_evidence_alignment:v2"]
    assert comparison["versions"]["v13"][2] == comparison["versions"]["v14"][2]  # matcher unchanged


def test_live_v14_equals_the_evaluated_b1nr_research_adapter(comparison):
    """No divergence between G20's research adapter and the production port on G20's frozen sets."""
    for split in ("dev", "holdout"):
        assert comparison["research_adapter_vs_live"][split] == {
            "v13_live_equals_g20_frozen_v13": True, "v14_live_equals_g20_frozen_b1nr": True}


@pytest.mark.parametrize("name", ["g20_dev", "g20_holdout", "g21_adversarial"])
def test_committed_v14_control_metrics_reproduce_live(comparison, name):
    import m11g20_admission as adm

    controls = json.loads((G21 / "adversarial_controls.json").read_text(encoding="utf-8"))["controls"] \
        if name == "g21_adversarial" else adm.load_controls(name.split("_")[1])
    agg = adm.aggregate([adm.evaluate_control(c, adm.POLICY_V13) for c in controls])
    assert agg["1_false_admissions"]["units_with_any_row"] == comparison["controls"][name]["v14"]["false_admission_units"]
    assert [agg["necessity_accuracy"]["correct"], agg["necessity_accuracy"]["scored"]] == \
        comparison["controls"][name]["v14"]["necessity"]


def test_g20_benchmarks(comparison):
    dev, hold = comparison["controls"]["g20_dev"], comparison["controls"]["g20_holdout"]
    assert (dev["v13"]["false_admission_units"], dev["v14"]["false_admission_units"]) == (26, 0)
    assert (hold["v13"]["false_admission_units"], hold["v14"]["false_admission_units"]) == (16, 1)
    assert (dev["v13"]["necessity"], dev["v14"]["necessity"]) == ([43, 46], [46, 46])
    assert (hold["v13"]["necessity"], hold["v14"]["necessity"]) == ([17, 19], [19, 19])
    assert dev["near_neighbour_pairs_correct"] == {"v13": [2, 12], "v14": [12, 12]}
    assert hold["near_neighbour_pairs_correct"] == {"v13": [0, 4], "v14": [4, 4]}
    for d in (dev, hold):
        assert d["lost_genuine_qualifications"] == [] and d["new_false_admissions"] == []
    assert hold["v14_residual_false_admissions"] == ["m11g20-h003/u0"]  # the documented on-call case


def test_original_v14_adversarial_results_are_preserved(original):
    """The ORIGINAL v14 run on the then-fresh adversarial set (preserved as recorded). Its two
    failures informed the Option B correction, so the 35 controls are DEVELOPMENT data now."""
    adv = original["controls"]["g21_adversarial"]
    assert (adv["v13"]["false_admission_units"], adv["v14"]["false_admission_units"]) == (17, 11)
    assert adv["new_false_admissions"] == []
    # Known v14 regressions vs v13: a negation in one clause declines the whole claim (a19), and
    # "preferred but not essential" is read as a negation (a20). Both stay visible as UnparsedClaims.
    assert adv["lost_genuine_qualifications"] == ["m11g21-a19/u0", "m11g21-a20/u0"]
    assert len(adv["v14_residual_false_admissions"]) == 11


def test_historical_compatibility(comparison):
    corp = comparison["corpora"]
    for name, d in corp.items():
        assert d["gold_regressed_ids"] == [], name
        assert d["span_text_errors_v14"] == 0, name
    assert corp["g16"]["gold_fixed_ids"] == ["m11g16-053"] and corp["g18"]["gold_fixed_ids"] == ["m11g18-25"]
    for name in ("g15", "m10d", "m10e", "g6", "g7", "8c_jobs", "m10_soti_manulife"):
        assert corp[name]["changed_ids"] == [], name
    sc = comparison["scoring"]
    for name, d in sc.items():
        assert d["status_changed_on_kept_rows"] == [] and d["eligibility_changed_on_kept_rows"] == [], name
        assert d["new_false_supported_candidates"] == [], name
    for name in ("g15", "g16", "8c:v1", "8c:v1.1", "m10"):
        assert sc[name]["score_changed"] == [] and sc[name]["denominator_changed"] == [], name
    assert sc["g18"]["became_undefined"] == ["m11g18-25/python_docker"]
    assert comparison["g17_guard"]["violations"] == []


def test_private_comparison_is_counts_only():
    def walk(obj, key=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, k)
        else:
            assert not isinstance(obj, list), key
            assert not isinstance(obj, str) or key == "note", key
    walk(json.loads((G21 / "private_v13_v14_aggregates.json").read_text(encoding="utf-8")))


def test_g20_evaluator_refuses_to_overwrite_frozen_v13_outputs():
    import evaluate_m11g20_false_qualification as g20

    with pytest.raises(SystemExit, match="v13 only"):
        g20.main()


# ---- G21 Option B: clause-local negation scope + optionality (red before the correction) -------------
def exact_rows(text: str) -> list[tuple]:
    """Sorted (label, necessity) per row; label = members joined, or the non-technical category."""
    out = []
    for members, category, nec in rows(text):
        out.append(("|".join(members) if members else category, nec))
    return sorted(out)


NEGATION_SCOPE_CASES = [
    # (text, expected exact rows) -- pinned BEFORE the correction
    ("A degree is not required; strong Python skills are.", [("language.python", R)]),
    ("TypeScript is preferred but not essential.", [("language.typescript", P)]),
    ("A degree is not required; Python experience is required.", [("language.python", R)]),
    ("A degree is not required; Python is used by our team.", []),
    ("Python experience is not required.", []),
    ("Python is preferred, but not required.", [("language.python", P)]),
    ("Python is optional but desirable.", [("language.python", P)]),
    ("Python is not required and is not considered.", []),
    ("You must be on call during weekends.", []),
    ("Our team prefers TypeScript for internal projects.", []),
]


@pytest.mark.parametrize("text,expected", NEGATION_SCOPE_CASES, ids=[t for t, _ in NEGATION_SCOPE_CASES])
def test_negation_scope_and_optionality(text, expected):
    assert exact_rows(text) == expected


def test_mixed_necessity_sentence_known_limitation():
    """'Experience with Java is required; Python is preferred.' -- both are admitted and Java is
    REQUIRED, but necessity is decided per CLAIM, so Python is also REQUIRED. Per-clause necessity
    needs per-conjunct rows (G16 decomposition territory); characterized explicitly, not fixed here."""
    assert exact_rows("Experience with Java is required; Python is preferred.") == [
        ("language.java", R), ("language.python", R)]


def test_negated_clause_is_masked_but_provenance_is_the_whole_claim():
    text = "A degree is not required; strong Python skills are."
    parsed = parse(text)
    (row,) = parsed.profile.requirements
    assert row.concept_id == "language.python" and row.necessity.value == R
    assert row.original_text == text and text[row.source_span.start:row.source_span.end] == text


def test_ellipsis_resolves_only_after_an_explicitly_negated_predicate():
    # 'X are.' alone never carries a necessity of its own
    assert refine_necessity("Strong Python skills are.", Necessity.PREFERRED) is Necessity.PREFERRED
    assert refine_necessity("A degree is not required; strong Python skills are.", Necessity.REQUIRED) \
        is Necessity.REQUIRED
    assert refine_necessity("A degree is not preferred; strong Python skills are.", Necessity.REQUIRED) \
        is Necessity.PREFERRED
    decision = qi.decide_qualification_intent("Our engineers are.", None)
    assert decision.role != "qual"


def test_optionality_never_promotes_preferred_to_required():
    for text in ("TypeScript is preferred but not essential.", "Python is preferred, but not required.",
                 "Docker is nice to have but not required."):
        assert {n for _, n in exact_rows(text)} == {P}, text


# ---- Option B: revised v14 results (the 35 adversarial controls are now development data) ------------
def test_revised_adversarial_meets_the_option_b_acceptance_criteria(comparison, original):
    rev, orig = comparison["controls"]["g21_adversarial"], original["controls"]["g21_adversarial"]
    assert rev["lost_genuine_qualifications"] == []                       # both losses corrected
    assert rev["new_false_admissions"] == []
    assert rev["v14"]["false_admission_units"] == 11 <= orig["v14"]["false_admission_units"]
    assert rev["v14_residual_false_admissions"] == orig["v14_residual_false_admissions"]
    assert rev["v14"]["necessity"] == [20, 20]                             # was [18, 18]
    assert rev["v14"]["unit_recall"] >= rev["v13"]["unit_recall"]
    assert rev["v14"]["source_spans_within_unit"] and not [k for k, v in rev["parse"].items() if not v["span_text_ok"]]


def test_revised_leaves_g20_history_scoring_and_private_identical_to_original_v14(comparison, original):
    for key in ("research_adapter_vs_live", "corpora", "scoring", "g17_guard"):
        assert comparison[key] == original[key], key
    for split in ("g20_dev", "g20_holdout"):
        assert comparison["controls"][split] == original["controls"][split], split
    a = json.loads((G21 / "private_v13_v14_aggregates.json").read_text(encoding="utf-8"))
    b = json.loads((G21 / "private_v13_v14_revised_aggregates.json").read_text(encoding="utf-8"))
    assert a == b


def test_negation_scope_examples_frozen_before_the_revision_and_results_pinned(comparison):
    import gold_integrity as gi

    res = gi.verify_frozen_file(G21 / "negation_scope_controls.json", G21 / "negation_scope_hash_freeze.json")
    assert res.method in ("raw", "canonical")
    doc = json.loads((G21 / "negation_scope_controls.json").read_text(encoding="utf-8"))
    assert "NOT an independent holdout" in doc["authorship_disclosure"]
    ns = comparison["negation_scope"]
    assert (ns["controls"], ns["correct_v13"], ns["correct_v14"]) == (16, 4, 14)
    failing = sorted(k for k, v in ns["results"].items() if not v["v14_correct"])
    assert failing == ["m11g21-n07", "m11g21-n16"]
    assert all(ns["results"][k]["expected_limitation"] for k in failing)  # flagged BEFORE the run
    assert all(v["v14_span_text_ok"] for v in ns["results"].values())


def test_private_revised_comparison_is_counts_only():
    def walk(obj, key=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, k)
        else:
            assert not isinstance(obj, list), key
            assert not isinstance(obj, str) or key == "note", key
    walk(json.loads((G21 / "private_v13_v14_revised_aggregates.json").read_text(encoding="utf-8")))


# ---- reproducibility of the preserved first-v14 record and of the revised comparison -----------------
def test_comparison_runner_pins_v13_and_refuses_to_overwrite_the_first_v14_record(monkeypatch):
    import evaluate_m11g21_v13_v14 as runner

    assert runner.V13_REF == "a2602820b21d521c7ac4006b6738224fde716e2c"
    monkeypatch.setattr(sys, "argv", ["evaluate_m11g21_v13_v14.py"])
    with pytest.raises(SystemExit, match="preserved FIRST-v14 record"):
        runner.main()


def test_first_v14_reverse_patch_applies_cleanly_to_exactly_the_three_production_files(tmp_path):
    import subprocess

    patch = G21 / "first_v14_reverse.patch"
    files = sorted(re.findall(r"^diff --git a/(\S+) ", patch.read_text(encoding="utf-8"), re.M))
    assert files == ["src/gitscore/jobs/parsing/necessity.py", "src/gitscore/jobs/parsing/parser.py",
                     "src/gitscore/jobs/parsing/qualification_intent.py"]
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    for rel in files:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes((REPO_ROOT / rel).read_bytes().replace(b"\r\n", b"\n"))
    # a Windows autocrlf checkout gives the patch CRLF line endings; apply an LF copy
    (tmp_path / "first_v14.patch").write_bytes(patch.read_bytes().replace(b"\r\n", b"\n"))
    subprocess.run(["git", "apply", "first_v14.patch"], cwd=tmp_path, check=True)
    first_parser = (tmp_path / "src/gitscore/jobs/parsing/parser.py").read_text(encoding="utf-8")
    assert "scoped_text" not in first_parser and "full_text" not in first_parser
    assert 'JOB_DESCRIPTION_PARSER_VERSION = "job_description_parser:v14"' in first_parser


def test_revised_report_labels_the_35_adversarial_controls_as_development_data(comparison, original):
    assert comparison["labels"]["g21_adversarial"].startswith("DEVELOPMENT data")
    assert "held" not in comparison["labels"]["g21_adversarial"].lower()
    assert original["labels"]["g21_adversarial"] == "newly authored synthetic (G21); not independent external validation"
