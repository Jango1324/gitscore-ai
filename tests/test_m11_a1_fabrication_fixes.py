"""Milestone 11-A1 -- narrow fabrication-safety fixes.

Approved scope (production-approval message): prevent (1) malformed,
non-technology prose fragments from being promoted into fabricated
`unresolved:<term>` concepts via `concepts.py::find_conservative_unknown_terms`'s
sibling-confirmed path, and (2) company/product narrative mentioning a
real technology from being converted into a scored applicant
qualification, while (3) preserving every genuine qualification that
explicitly mentions the same technologies/experience. Deliberately
narrow and generalizable -- no employer-specific rule, no broad
narrative blacklist, no schema/matcher/scoring change, no line-wrap
fix (tracked separately per the production-approval message).

Written and run against BASELINE (pre-fix) code first, per the required
process, to confirm each `# FAILS ON BASELINE` case actually fails
before any production code changes, then re-run green after the fix.
"""
from __future__ import annotations

from gitscore.jobs import Necessity, parse_job_description, parse_job_description_with_diagnostics
from gitscore.jobs.parsing.parser import JOB_DESCRIPTION_PARSER_VERSION


def test_parser_version_bumped_to_v9():
    assert JOB_DESCRIPTION_PARSER_VERSION == "job_description_parser:v9"


def _concept_ids(profile):
    ids = set()
    for r in profile.requirements:
        if r.concept_id is not None:
            ids.add(r.concept_id)
        ids.update(r.alternative_concept_ids)
    return ids


# ---------------------------------------------------------------------------
# 1. Malformed-fragment fabrication (find_conservative_unknown_terms)
# ---------------------------------------------------------------------------


def test_bare_pronoun_leftover_is_not_promoted_to_an_unresolved_concept():
    # FAILS ON BASELINE: 'unresolved:our' is fabricated from the bare
    # pronoun "our" left over after splitting on "and"/",".
    profile = parse_job_description(
        "The system uses PostgreSQL, our main database, for storage.\n"
    )
    ids = _concept_ids(profile)
    assert "database.postgresql" in ids
    for cid in ids:
        if cid.startswith("unresolved:"):
            raise AssertionError(f"fabricated unresolved concept from ordinary prose: {cid!r}")


def test_ordinary_descriptive_fragment_is_not_promoted_to_an_unresolved_concept():
    # FAILS ON BASELINE: "is required" -> 'unresolved:is_required'.
    profile = parse_job_description(
        "Experience with PostgreSQL, and a willingness to learn, is required.\n"
    )
    ids = _concept_ids(profile)
    assert "database.postgresql" in ids
    for cid in ids:
        if cid.startswith("unresolved:"):
            raise AssertionError(f"fabricated unresolved concept from ordinary prose: {cid!r}")


def test_possessive_descriptive_phrase_is_not_promoted_to_an_unresolved_concept():
    # FAILS ON BASELINE: "our internal tooling" -> 'unresolved:our_internal_tooling'.
    profile = parse_job_description(
        "Must know PostgreSQL, Redis, and our internal tooling.\n"
    )
    ids = _concept_ids(profile)
    assert "database.postgresql" in ids
    assert "database.redis" in ids
    for cid in ids:
        if cid.startswith("unresolved:"):
            raise AssertionError(f"fabricated unresolved concept from ordinary prose: {cid!r}")


def test_legitimate_unknown_technology_name_still_promoted_sibling_confirmed_path():
    """Regression anchor -- `tests/test_job_requirement_preservation.py
    ::test_mixed_known_and_unknown_combination_unaffected`'s EXACT shape
    (the sibling-confirmed promotion path, not the enumeration-cue path):
    a real concept (React) in the same comma list unlocks promotion of
    genuinely technology-SHAPED unknown items (Vue, SomeNewLibrary --
    both Capitalized) -- must NOT be suppressed by the new shape gate.
    """
    profile = parse_job_description("Requirements:\n- Experience with React, Vue, and SomeNewLibrary\n")
    ids = _concept_ids(profile)
    assert "framework.react" in ids
    assert "unresolved:vue" in ids
    assert "unresolved:somenewlibrary" in ids


def test_legitimate_unknown_technology_name_still_promoted_with_known_orchestrator_sibling():
    """Regression anchor -- `tests/test_job_parser.py
    ::test_...someunknownorchestrator...` (a synthetic, guaranteed-
    unregistered, Capitalized term) must still promote."""
    profile = parse_job_description(
        "Requirements:\n- Experience with Python, SomeUnknownOrchestrator, and Docker\n"
    )
    ids = _concept_ids(profile)
    assert "language.python" in ids
    assert "infra.docker" in ids
    assert any(cid.startswith("unresolved:someunknownorchestrator") for cid in ids)


def test_enumeration_cue_path_unaffected_spi_i2c_uart():
    """Regression anchor -- `tests/test_job_requirement_preservation.py
    ::test_unknown_technical_and_list_mints_three_unresolved_rows`
    (the SEPARATE, ALREADY-shape-gated enumeration-cue path, `mentions`
    empty) -- must be completely unaffected by this fix."""
    profile = parse_job_description(
        "Requirements:\n- Familiarity with microcontroller peripherals such as SPI, I2C, and UART\n"
    )
    ids = _concept_ids(profile)
    assert ids == {"unresolved:spi", "unresolved:i2c", "unresolved:uart"}


# ---------------------------------------------------------------------------
# 2. Company/product narrative generalization
# ---------------------------------------------------------------------------


def test_company_narrative_backend_frontend_phrasing_is_not_a_requirement():
    # FAILS ON BASELINE: fabricates JobRequirement(necessity=REQUIRED,
    # concept_id='framework.react') from pure company narrative.
    result = parse_job_description_with_diagnostics(
        "We move fast -- you will wear a lot of hats here, touching everything "
        "from our Node.js backend to our React frontend.\n"
    )
    ids = _concept_ids(result.profile)
    assert "framework.react" not in ids
    assert any("backend" in c.text or "frontend" in c.text for c in result.unparsed_claims)


def test_company_history_years_of_experience_narrative_is_not_a_requirement():
    """Regression anchor, NOT a new fix target -- already passes on
    baseline (M10E's existing "we've built" cue already matches this
    phrasing when NOT fragmented by the separately-tracked line-wrap
    defect, confirmed by direct trace during this milestone's Phase 1).
    Company-history narrative naming a technology AND an experience-
    years figure together must not become either a technology OR an
    experience requirement."""
    result = parse_job_description_with_diagnostics(
        "Our engineering culture values deep ownership. We've built our platform "
        "on Go and PostgreSQL over the past 6 years, and our team genuinely loves "
        "talking shop about distributed systems at lunch.\n"
    )
    reqs = result.profile.requirements
    assert reqs == ()
    assert len(result.unparsed_claims) == 1


def test_company_narrative_codebase_infrastructure_phrasing_is_not_a_requirement():
    result = parse_job_description_with_diagnostics(
        "Join our small team. Our infrastructure runs on Kubernetes and our codebase "
        "is primarily TypeScript.\n"
    )
    ids = _concept_ids(result.profile)
    assert "infra.kubernetes" not in ids
    assert "language.typescript" not in ids


# ---------------------------------------------------------------------------
# 3. Genuine qualifications explicitly mentioning the SAME technologies
#    must still survive -- the precedence a narrative fix must never break.
# ---------------------------------------------------------------------------


def test_explicit_required_marker_survives_even_with_our_nearby():
    """Local REQUIRED/PREFERRED marker always wins, unconditionally,
    checked before any narrative-cue logic -- even when the claim ALSO
    contains an "our" + infra-noun phrase that would otherwise match the
    widened company-narrative cue."""
    profile = parse_job_description("Experience with our React codebase is required.\n")
    ids = _concept_ids(profile)
    assert "framework.react" in ids
    react_rows = [r for r in profile.requirements if r.concept_id == "framework.react"]
    assert react_rows[0].necessity == Necessity.REQUIRED


def test_genuine_technology_qualification_is_preserved():
    profile = parse_job_description("Requirements:\n- Experience with React and Node.js is required.\n")
    ids = _concept_ids(profile)
    assert "framework.react" in ids


def test_genuine_experience_requirement_is_preserved():
    profile = parse_job_description("Requirements:\n- 5+ years of professional Java experience is required.\n")
    ids = _concept_ids(profile)
    assert "language.java" in ids
    java_rows = [r for r in profile.requirements if r.concept_id == "language.java"]
    assert java_rows[0].necessity == Necessity.REQUIRED


def test_unsectioned_posting_genuine_qualification_still_admitted():
    """The genuinely-unsectioned ('no heading anywhere') fallback case
    (M10E's own case (c)) must be completely unaffected by either fix."""
    profile = parse_job_description("Experience with Python and PostgreSQL is required.\n")
    ids = _concept_ids(profile)
    assert {"language.python", "database.postgresql"} <= ids


def test_mixed_company_narrative_and_explicit_qualification_in_one_posting():
    """A posting mixing a narrative paragraph (naming React) with a
    separate, explicit Requirements section (naming Python) must
    suppress ONLY the narrative mention, never the genuine one."""
    text = (
        "Our platform's frontend is built with React and our backend runs on Go.\n\n"
        "Requirements:\n"
        "- Experience with Python is required\n"
    )
    result = parse_job_description_with_diagnostics(text)
    ids = _concept_ids(result.profile)
    assert "framework.react" not in ids
    assert "language.python" in ids
    python_rows = [r for r in result.profile.requirements if r.concept_id == "language.python"]
    assert python_rows[0].necessity == Necessity.REQUIRED


def test_previously_correct_alternative_groups_still_correct_soti_manulife():
    """Regression anchor -- the two real postings' OWN genuine
    alternative-group requirements (M10D/M10E) must survive unaffected."""
    soti_required_skills = (
        "Required skills:\n"
        "- Basic knowledge of programming in one or more of the following "
        "programming languages: C, C++, Java, JavaScript, SQL, Ruby, Rust, Lua, Haskell\n"
    )
    profile = parse_job_description(soti_required_skills)
    alt_rows = [r for r in profile.requirements if r.is_alternative_group]
    assert len(alt_rows) == 1
    assert len(alt_rows[0].alternative_concept_ids) == 9

    manulife_any_of = (
        "Required Qualifications:\n"
        "- Experience with at least one programming language (e.g., Java, Python, Go, JavaScript)\n"
    )
    profile2 = parse_job_description(manulife_any_of)
    alt_rows2 = [r for r in profile2.requirements if r.is_alternative_group]
    assert len(alt_rows2) == 1
    assert alt_rows2[0].alternative_concept_ids == (
        "language.go", "language.java", "language.javascript", "language.python",
    )
