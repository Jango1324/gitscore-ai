"""Milestone 10D -- alternative-requirement semantics.

Covers the approved design in
`docs/evaluation/MILESTONE_10D_ALTERNATIVE_SEMANTICS.md` (§6.7's five
STOP questions, all approved): an explicit ANY-of trigger-phrase path
for Root Cause 4 ("at least one programming language (e.g., ...)" with
no literal "or" at all), an idiom guard for Root Cause 5 ("one or more
of the following programming languages: ..." -- the idiom's own "or"
must never split as a list separator), and a shape-gated fix to a
previously-unconditional `unresolved:<term>` promotion branch that
could fabricate a garbled id. All three live entirely in
`jobs/parsing/alternatives.py`; `JOB_DESCRIPTION_PARSER_VERSION` bumps
`v6` -> `v7` (`jobs/parsing/parser.py`).

The 41 controls in `evaluation/m10d/alternative_controls.json` were
authored BEFORE this implementation existed (the milestone's own
evaluation-first design phase) and are loaded here verbatim, never
edited to match whatever the implementation happens to do -- a
mismatch here means the implementation is wrong, not the control.
Three controls (`m10d-e1`, `m10d-e2`, `m10d-h6`) are annotated
`conservative_fallback_expected: "unsupported_mixed"` -- a genuine
MIXED AND/OR shape ("Python or Java and SQL") this implementation
explicitly does NOT attempt to solve (Root Cause 6, deferred). Those
three are tested separately, pinning their CURRENT, still-imperfect,
non-fabricating behavior, rather than asserted against an idealized
outcome this implementation does not claim to produce.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gitscore.jobs import parse_job_description
from gitscore.jobs.parsing.alternatives import classify_alternative_claim
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION

CORPUS_PATH = Path(__file__).resolve().parent.parent / "evaluation" / "m10d" / "alternative_controls.json"
CORPUS = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))["controls"]
UNSUPPORTED_MIXED_IDS = {"m10d-e1", "m10d-e2", "m10d-h6"}
DETERMINATE_CONTROLS = [c for c in CORPUS if c["id"] not in UNSUPPORTED_MIXED_IDS]
MIXED_CONTROLS = {c["id"]: c for c in CORPUS if c["id"] in UNSUPPORTED_MIXED_IDS}


# ---------------------------------------------------------------------------
# 1. All 41 corpus controls (38 determinate + 3 pinned-as-unsupported)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("control", DETERMINATE_CONTROLS, ids=[c["id"] for c in DETERMINATE_CONTROLS])
def test_m10d_corpus_control(control):
    claim = classify_alternative_claim(control["text"])
    expected_ids = control.get("expected_concept_ids")
    expected_count = control.get("expected_requirement_group_count")
    logical_structure = control["logical_structure"]

    if expected_ids is None:
        assert claim.kind in ("not_technical", "unsafe"), (
            f"{control['id']}: expected no fabricated group, got {claim}"
        )
        assert expected_count in (0, None)
        return

    if logical_structure == "ALL":
        # A true AND list is never a `classify_alternative_claim()`
        # group at all -- it correctly stays `not_technical` there and
        # only produces its independent rows one level up, through the
        # ordinary per-claim concept-mention pipeline
        # (`jobs/parsing/parser.py::_requirements_from_claim`).
        assert claim.kind == "not_technical", f"{control['id']}: {claim}"
        from gitscore.jobs.parsing.concepts import find_concept_mentions

        mentions = {m.concept_id for m in find_concept_mentions(control["text"])}
        assert mentions == set(expected_ids), f"{control['id']}: {mentions}"
        return

    assert sorted(claim.concept_ids) == sorted(expected_ids), f"{control['id']}: {claim}"
    assert claim.kind == "technical"
    # Exactly one logical ANY-of group per control (never split into
    # more than one `JobRequirement`-equivalent group) -- the
    # single-group-per-claim invariant Phase 4 requires.
    if expected_count is not None:
        assert expected_count == 1


def test_m10d_corpus_control_e1_mixed_and_or_stays_safe_not_fabricating():
    """Root Cause 6 -- NOT fixed by this milestone. Pinned to the
    CURRENT, measured behavior (still flattens the mandatory "and SQL"
    clause into the OR-group) so a future change to this known
    limitation is a deliberate decision, not a silent drift."""
    control = MIXED_CONTROLS["m10d-e1"]
    claim = classify_alternative_claim(control["text"])
    assert claim.kind == "technical"
    assert sorted(claim.concept_ids) == ["language.java", "language.python", "language.sql"]


def test_m10d_corpus_control_e2_mixed_and_or_stays_safe_not_fabricating():
    control = MIXED_CONTROLS["m10d-e2"]
    claim = classify_alternative_claim(control["text"])
    assert claim.kind == "technical"
    assert sorted(claim.concept_ids) == ["database.postgresql", "language.python", "unresolved:mysql"]


def test_m10d_corpus_control_h6_two_clauses_one_bullet_stays_unsafe_not_fabricating():
    """Two list-shaped clauses in one bullet ("Java or Python, plus one
    or more scripting languages") -- Root Cause 6 territory. Must
    remain the conservative `unsafe` placeholder, never a fabricated
    `unresolved:plus_one`/`unresolved:more_scripting_languages`."""
    control = MIXED_CONTROLS["m10d-h6"]
    claim = classify_alternative_claim(control["text"])
    assert claim.kind == "unsafe"
    assert claim.concept_ids == ()


# ---------------------------------------------------------------------------
# 2/3. Exact SOTI / Manulife source sentences (verbatim, from the
# committed evaluation/m10/source/*.txt transcriptions)
# ---------------------------------------------------------------------------

def test_soti_exact_sentence_is_one_safely_constructed_any_of_group():
    text = (
        "Basic knowledge of programming in one or more of the following "
        "programming languages: C, C++, Java, JavaScript, SQL, Ruby, Rust, Lua, Haskell"
    )
    claim = classify_alternative_claim(text)
    assert claim.kind == "technical"
    assert claim.concept_ids == (
        "language.c",
        "language.cpp",
        "language.java",
        "language.javascript",
        "language.ruby",
        "language.rust",
        "language.sql",
        "unresolved:haskell",
        "unresolved:lua",
    )


def test_soti_exact_sentence_end_to_end_produces_one_required_requirement():
    text = (
        "Required skills:\n"
        "- Basic knowledge of programming in one or more of the following "
        "programming languages: C, C++, Java, JavaScript, SQL, Ruby, Rust, Lua, Haskell\n"
    )
    profile = parse_job_description(text)
    alt_rows = [r for r in profile.requirements if r.is_alternative_group]
    assert len(alt_rows) == 1
    assert len(alt_rows[0].alternative_concept_ids) == 9


def test_manulife_exact_sentence_is_one_any_of_group_not_four_rows():
    text = "Experience with at least one programming language (e.g., Java, Python, Go, JavaScript)"
    claim = classify_alternative_claim(text)
    assert claim.kind == "technical"
    assert claim.concept_ids == ("language.go", "language.java", "language.javascript", "language.python")


def test_manulife_exact_sentence_end_to_end_produces_one_required_requirement():
    text = (
        "Required Qualifications:\n"
        "- Experience with at least one programming language (e.g., Java, Python, Go, JavaScript)\n"
    )
    profile = parse_job_description(text)
    alt_rows = [r for r in profile.requirements if r.is_alternative_group]
    assert len(alt_rows) == 1
    assert alt_rows[0].alternative_concept_ids == (
        "language.go",
        "language.java",
        "language.javascript",
        "language.python",
    )
    # Previously-lost "Go" row count check (Root Cause 4's secondary
    # paren-pollution defect, §1.3 of the design doc) -- confirmed not
    # a separate `unresolved:go` row anywhere in the profile.
    assert not any(r.concept_id == "unresolved:go" for r in profile.requirements)


# ---------------------------------------------------------------------------
# 4. Existing general_swe_01 OR-group (frozen gold positive control)
# ---------------------------------------------------------------------------

def test_general_swe_01_or_group_is_unchanged():
    claim = classify_alternative_claim("Proficiency in at least one of Python, Java, or C++")
    assert claim.kind == "technical"
    assert claim.concept_ids == ("language.cpp", "language.java", "language.python")


# ---------------------------------------------------------------------------
# 5. Both previously reproduced fabricated-unresolved variants
# ---------------------------------------------------------------------------

def test_idiom_fabrication_variant_no_longer_fabricates_unresolved_one():
    claim = classify_alternative_claim(
        "Experience with one or more of the following languages: Python, Java, Go"
    )
    assert claim.kind == "technical"
    assert claim.concept_ids == ("language.go", "language.java", "language.python")
    assert "unresolved:one" not in claim.concept_ids


def test_idiom_fabrication_colon_variant_no_longer_fabricates_garbled_ids():
    claim = classify_alternative_claim("Knowledge of one or more of: C, C++, Java")
    assert claim.kind == "technical"
    assert claim.concept_ids == ("language.c", "language.cpp", "language.java")
    assert "unresolved:one" not in claim.concept_ids
    assert not any(cid.startswith("unresolved:more") for cid in claim.concept_ids)


# ---------------------------------------------------------------------------
# 6/7. C vs C++, Java vs JavaScript (concept-resolution hazards --
# regression guards, must remain unaffected by this milestone)
# ---------------------------------------------------------------------------

def test_c_versus_cpp_both_resolve_distinctly():
    claim = classify_alternative_claim("Experience with C or C++")
    assert claim.kind == "technical"
    assert claim.concept_ids == ("language.c", "language.cpp")


def test_java_versus_javascript_both_resolve_distinctly():
    claim = classify_alternative_claim("Java or JavaScript experience")
    assert claim.kind == "technical"
    assert claim.concept_ids == ("language.java", "language.javascript")


# ---------------------------------------------------------------------------
# 8. Recognized concept mixed with a genuinely unknown technology
# ---------------------------------------------------------------------------

def test_recognized_concept_mixed_with_genuinely_unknown_technology():
    claim = classify_alternative_claim("Experience with Java, Python, or SomeNewRuntime")
    assert claim.kind == "technical"
    assert claim.concept_ids == ("language.java", "language.python", "unresolved:somenewruntime")


# ---------------------------------------------------------------------------
# 9. Bare "at least one" in non-enumeration prose must NOT become an
# ANY-of technology group
# ---------------------------------------------------------------------------

def test_bare_at_least_one_in_non_enumeration_prose_is_not_a_fake_any_of_group():
    claim = classify_alternative_claim("Experience with at least one year of experience with Python")
    assert claim.kind == "not_technical"


def test_at_least_one_backend_framework_and_one_database_is_not_fabricated():
    """Generic category nouns ("backend framework", "database"), not
    named technologies -- the trigger phrase alone must never promote
    them."""
    claim = classify_alternative_claim("Familiarity with at least one backend framework and one database")
    assert claim.kind == "not_technical"


# ---------------------------------------------------------------------------
# 10. Illustrative vs. exhaustive lists
# ---------------------------------------------------------------------------

def test_illustrative_parenthetical_list_resolves_only_the_named_items():
    """Manulife's "(e.g., ...)" list is illustrative, not exhaustive --
    this implementation resolves ONLY what the posting actually named,
    never implying a technology outside the list is unacceptable (no
    policy exists, or is proposed, for extrapolating beyond it)."""
    claim = classify_alternative_claim("At least one programming language (e.g., Java, Python, Go, JavaScript)")
    assert claim.kind == "technical"
    assert claim.concept_ids == ("language.go", "language.java", "language.javascript", "language.python")


def test_exhaustive_colon_list_resolves_exactly_the_named_items():
    claim = classify_alternative_claim("One of the following: Java, Kotlin, Swift")
    assert claim.kind == "technical"
    assert claim.concept_ids == ("language.java", "language.kotlin", "language.swift")


# ---------------------------------------------------------------------------
# 11. No regression to AND requirements
# ---------------------------------------------------------------------------

def test_and_requirement_stays_independent_rows_not_a_fake_any_of_group():
    claim = classify_alternative_claim("Experience with Python and SQL")
    assert claim.kind == "not_technical"

    profile = parse_job_description("Requirements:\n- Experience with Python and SQL\n")
    single_concept_ids = {r.concept_id for r in profile.requirements if r.concept_id is not None}
    assert single_concept_ids == {"language.python", "language.sql"}
    assert not any(r.is_alternative_group for r in profile.requirements)


def test_oxford_comma_and_list_stays_independent_rows():
    claim = classify_alternative_claim("Experience with Java, Python, and Go")
    assert claim.kind == "not_technical"


# ---------------------------------------------------------------------------
# 12. Source-span preservation and determinism
# ---------------------------------------------------------------------------

def test_source_span_and_original_text_preserved_for_an_any_of_group():
    text = "Requirements:\n- Experience with at least one programming language (e.g., Java, Python, Go)\n"
    profile = parse_job_description(text)
    alt_rows = [r for r in profile.requirements if r.is_alternative_group]
    assert len(alt_rows) == 1
    row = alt_rows[0]
    assert row.original_text == "Experience with at least one programming language (e.g., Java, Python, Go)"
    assert row.source_span is not None
    assert text[row.source_span.start : row.source_span.end] == row.original_text


def test_classify_alternative_claim_is_deterministic():
    text = "Basic knowledge of programming in one or more of the following programming languages: C, C++, Java"
    first = classify_alternative_claim(text)
    second = classify_alternative_claim(text)
    assert first == second


# ---------------------------------------------------------------------------
# 13. Single ANY-of requirement counted once in the assessable
# denominator (never one row per alternative)
# ---------------------------------------------------------------------------

def test_any_of_group_is_exactly_one_requirement_in_the_profile():
    text = "Requirements:\n- Experience with at least one programming language (e.g., Java, Python, Go, JavaScript)\n"
    profile = parse_job_description(text)
    matching_rows = [r for r in profile.requirements if "programming language" in r.original_text]
    assert len(matching_rows) == 1
    assert matching_rows[0].is_alternative_group
    assert len(matching_rows[0].alternative_concept_ids) == 4


# ---------------------------------------------------------------------------
# Version bump
# ---------------------------------------------------------------------------

def test_parser_version_bumped_to_v7():
    assert JOB_DESCRIPTION_PARSER_VERSION == "job_description_parser:v7"
