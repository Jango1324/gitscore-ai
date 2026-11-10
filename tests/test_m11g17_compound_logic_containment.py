"""Milestone 11-G17 -- safe compound-logic containment (parser v13).

Written BEFORE the production change, red against parser v12. Every test
uses the real parser, matcher and assessor; nothing is simulated.

Containment contract (Option D as evaluated in M11-G16, user decision for
G17): a structurally mixed AND/OR claim is routed to the parser's EXISTING
Milestone 6B.1 "unsafe" fallback -- a NON-SCOREABLE placeholder
(`category="alternative_requirement"`, no concept, no alternatives,
PARTIALLY_OBSERVABLE, always NOT_ASSESSABLE, never in the denominator,
shown as `interpretation_status="unparsed_placeholder"`). It keeps the
claim's original text, source span and necessity. Requirement 8 ("declined
claims do not become JobRequirements") is enforced as "never a SCOREABLE
JobRequirement".
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "src", REPO_ROOT / "scripts" / "evaluation_lib"):
    sys.path.insert(0, str(_p))

from gitscore.assessment import assess_job  # noqa: E402
from gitscore.jobs.parsing.parser import (  # noqa: E402
    JOB_DESCRIPTION_PARSER_VERSION,
    parse_job_description,
    parse_job_description_with_diagnostics,
)
from gitscore.jobs.types import GithubObservability, Necessity  # noqa: E402
from gitscore.matching import MatchStatus, match_job  # noqa: E402
from m11g15_or_scoring import candidate_profile  # noqa: E402

PY, GO, DOCKER, K8S, PG = ("language.python", "language.go", "infra.docker", "infra.kubernetes",
                           "database.postgresql")


def _assess(text: str, evidence: list[str]):
    profile = parse_job_description(text)
    analysis = match_job(candidate_profile(evidence), profile)
    return profile, analysis, assess_job(analysis)


def _is_contained_placeholder(r) -> bool:
    return (r.category == "alternative_requirement" and r.concept_id is None and not r.alternative_concept_ids
            and r.github_observability == GithubObservability.PARTIALLY_OBSERVABLE)


def _concept_sets(profile) -> list[set[str]]:
    return [set(r.alternative_concept_ids) or ({r.concept_id} if r.concept_id else set())
            for r in profile.requirements]


def test_parser_version_is_v13():
    # G17 bumped v12 -> v13. M11-G21 then bumped v13 -> v14 (qualification-intent guard); G17's
    # containment code is untouched -- only the literal tracks the current version.
    assert JOB_DESCRIPTION_PARSER_VERSION == "job_description_parser:v14"


# 1. (A OR B) AND C cannot be satisfied by C alone -----------------------------
def test_or_then_and_not_satisfied_by_the_conjunct_alone():
    profile, analysis, assessment = _assess("Experience with Docker or Kubernetes, and Python, is required.", [PY])
    assert analysis.supported_count == 0
    assert assessment.alignment_score is None
    assert {PY, DOCKER, K8S} not in _concept_sets(profile)


# 2. A AND (B OR C) cannot be satisfied by A alone -----------------------------
def test_and_then_or_not_satisfied_by_the_single_conjunct():
    _, analysis, assessment = _assess("Experience with Python and either Docker or Kubernetes is required.", [PY])
    assert analysis.supported_count == 0
    assert assessment.alignment_score is None


# 3. (A OR B) AND (C OR D) never becomes a flat OR list -----------------------
def test_or_and_or_never_flattened():
    profile = parse_job_description("Experience with Python or Go, and Docker or Kubernetes, is required.")
    assert all(len(s) < 4 for s in _concept_sets(profile))
    assert [_is_contained_placeholder(r) for r in profile.requirements] == [True]


# 4. Genuine simple A OR B unchanged -------------------------------------------
def test_simple_or_still_supported():
    profile, analysis, assessment = _assess("Experience with Docker or Kubernetes is required.", [DOCKER])
    assert _concept_sets(profile) == [{DOCKER, K8S}]
    assert analysis.requirement_matches[0].status == MatchStatus.SUPPORTED
    assert assessment.alignment_score == 100


# 5. Genuine simple A AND B unchanged ------------------------------------------
def test_simple_and_unchanged():
    profile, analysis, assessment = _assess("Experience with Python and Docker is required.", [PY])
    assert _concept_sets(profile) == [{PY}, {DOCKER}]
    assert (analysis.supported_count, assessment.assessable_count, assessment.alignment_score) == (1, 2, 50)


# 6. Ambiguous precedence declines ---------------------------------------------
def test_ambiguous_precedence_declines():
    profile = parse_job_description("Python and Docker or Kubernetes experience required.")
    assert [_is_contained_placeholder(r) for r in profile.requirements] == [True]


# 7. Declined claim keeps its exact text and source span -----------------------
def test_declined_claim_keeps_text_and_span():
    text = "Experience with Docker or Kubernetes, and Python, is required."
    (row,) = parse_job_description(text).requirements
    assert row.original_text == text
    assert text[row.source_span.start:row.source_span.end] == text


# 8. Declined claim is never a SCOREABLE JobRequirement -------------------------
def test_declined_claim_is_never_scoreable():
    profile, analysis, _ = _assess("Experience with Python and either Docker or Kubernetes is required.",
                                   [PY, DOCKER, K8S])
    (row,) = profile.requirements
    assert _is_contained_placeholder(row)
    assert analysis.requirement_matches[0].status == MatchStatus.NOT_ASSESSABLE


# 9. Declined claim never enters the denominator -------------------------------
def test_declined_claim_excluded_from_denominator():
    text = "Requirements:\n- Experience with Docker or Kubernetes, and Python\n- PostgreSQL experience"
    _, analysis, assessment = _assess(text, [PY, DOCKER, PG])
    assert assessment.assessable_count == 1
    assert assessment.alignment_score == 100
    assert analysis.not_assessable_count == 1


# 10. No fabricated REQUIRED: REQUIRED / PREFERRED / UNKNOWN --------------------
@pytest.mark.parametrize("text, expected", [
    ("Experience with Docker or Kubernetes, and Python, is required.", Necessity.REQUIRED),
    ("Experience with Python or Go, and Docker or Kubernetes, is preferred.", Necessity.PREFERRED),
])
def test_declined_claim_keeps_stated_necessity(text, expected):
    (row,) = parse_job_description(text).requirements
    assert _is_contained_placeholder(row)
    assert row.necessity == expected


def test_unknown_necessity_stays_unparsed_never_required():
    text = "Requirements:\n- Python experience\n\nTeam notes:\n- Docker or Kubernetes, and Go"
    parsed = parse_job_description_with_diagnostics(text)
    mixed_rows = [r for r in parsed.profile.requirements if "Kubernetes" in r.original_text]
    assert mixed_rows == []
    assert any("Kubernetes" in c.text for c in parsed.unparsed_claims)


# 11. Narrative protections unchanged ------------------------------------------
def test_company_narrative_still_produces_no_requirement():
    assert parse_job_description("Our platform uses Docker or Kubernetes and Python.").requirements == ()


# 12. Unrelated qualifications in the same job remain assessable ---------------
def test_unrelated_requirements_stay_assessable():
    text = "Requirements:\n- Experience with Docker or Kubernetes, and Python\n- PostgreSQL experience\n- Go experience"
    profile, analysis, _ = _assess(text, [PG])
    assessable = [m for m in analysis.requirement_matches if m.status != MatchStatus.NOT_ASSESSABLE]
    assert {m.requirement.concept_id for m in assessable} >= {PG}
    assert any(m.status == MatchStatus.SUPPORTED and m.requirement.concept_id == PG for m in assessable)


# Diagnostic visibility: a declined claim stays visible to users ---------------
def test_declined_claim_visible_as_unparsed_placeholder_diagnostic():
    from gitscore.api.serialization import serialize_requirement_match
    profile = parse_job_description("Experience with Docker or Kubernetes, and Python, is required.")
    (match,) = match_job(candidate_profile([PY, DOCKER]), profile).requirement_matches
    out = serialize_requirement_match(match)
    assert out.status == "not_assessable"
    assert out.interpretation_status == "unparsed_placeholder"
    assert out.text == "Experience with Docker or Kubernetes, and Python, is required."
    assert out.necessity == "required"


# No declined claim re-enters scoring through another parser path ------------
def test_declined_claims_never_reenter_scoring():
    controls = json.loads((REPO_ROOT / "evaluation" / "m11g16" / "compound_logic_controls.json")
                          .read_text(encoding="utf-8"))["controls"]
    for c in controls:
        profile = parse_job_description(c["text"])
        placeholder_spans = {r.source_span for r in profile.requirements
                             if r.category == "alternative_requirement"}
        for r in profile.requirements:
            if r.category != "alternative_requirement" and (r.concept_id or r.alternative_concept_ids):
                assert r.source_span not in placeholder_spans, c["id"]


# Whole-population regression: live v13 == G16's evaluated Option D -----------
def test_live_parser_reproduces_g16_option_d_rows_on_all_58_controls():
    controls = json.loads((REPO_ROOT / "evaluation" / "m11g16" / "compound_logic_controls.json")
                          .read_text(encoding="utf-8"))["controls"]
    g16 = json.loads((REPO_ROOT / "evaluation" / "m11g16" / "compound_logic_report.json")
                     .read_text(encoding="utf-8"))["results"]
    mismatches = []
    live_rows = {}
    for c in controls:
        live = [{"members": sorted(r.alternative_concept_ids) if r.alternative_concept_ids
                 else ([r.concept_id] if r.concept_id else []),
                 "necessity": r.necessity.value, "category": r.category}
                for r in parse_job_description(c["text"]).requirements]
        live_rows[c["id"]] = live
        expected = [{k: row[k] for k in ("members", "necessity", "category")}
                    for row in g16[c["id"]]["D_structural_guard"]["rows"]]
        if live != expected:
            mismatches.append(c["id"])
    if JOB_DESCRIPTION_PARSER_VERSION == "job_description_parser:v13":
        assert mismatches == []
    else:
        # M11-G21 (v14): the qualification-intent guard declines exactly one G16 control -- the
        # responsibility sentence 053 ("You will maintain services ..."), which G16 gold labels
        # is_qualification=False. Every other control (incl. all G17-contained compound rows)
        # must still equal G16's option D exactly.
        assert mismatches == ["m11g16-053"]
        assert live_rows["m11g16-053"] == []
