"""Milestone 6B Parts 5/6/7/8/9/10/12/13/14/15 -- unit tests for the
pure functions jobs/parsing/parser.py orchestrates.
"""
from gitscore.jobs.models import JobRequirement, SourceSpan
from gitscore.jobs.parsing.alternatives import classify_alternative_claim, contains_alternative_marker
from gitscore.jobs.parsing.concepts import find_concept_mentions, find_conservative_unknown_terms
from gitscore.jobs.parsing.confidence import confidence_for
from gitscore.jobs.parsing.dedup import deduplicate_requirements
from gitscore.jobs.parsing.experience import find_experience_qualifier
from gitscore.jobs.parsing.importance import infer_importance
from gitscore.jobs.parsing.necessity import infer_necessity
from gitscore.jobs.parsing.non_technical import find_non_technical_match
from gitscore.jobs.parsing.observability import observability_for_non_technical, observability_for_technical
from gitscore.jobs.types import GithubObservability, Importance, Necessity, ParserConfidence


# ---------------------------------------------------------------------------
# Concept mentions (Part 5) -- known concepts resolve through the existing registry
# ---------------------------------------------------------------------------

def test_postgres_alias_resolves():
    mentions = find_concept_mentions("Experience with Postgres")
    assert [m.concept_id for m in mentions] == ["database.postgresql"]


def test_pytorch_alias_resolves():
    mentions = find_concept_mentions("Deep experience with PyTorch")
    assert [m.concept_id for m in mentions] == ["ml.framework.pytorch"]


def test_nextjs_resolves():
    mentions = find_concept_mentions("Built with Next.js")
    assert [m.concept_id for m in mentions] == ["framework.nextjs"]


def test_ros2_resolves():
    mentions = find_concept_mentions("Hands-on ROS2 experience")
    assert [m.concept_id for m in mentions] == ["robotics.ros2"]


def test_cuda_and_cpp_resolve():
    mentions = find_concept_mentions("CUDA and C++ experience required")
    assert {m.concept_id for m in mentions} == {"platform.cuda", "language.cpp"}


def test_multiple_distinct_concepts_in_one_claim():
    mentions = find_concept_mentions("Experience with Python, PostgreSQL, and Docker")
    assert {m.concept_id for m in mentions} == {"language.python", "database.postgresql", "infra.docker"}


# ---------------------------------------------------------------------------
# Alias safety (Part 6) -- reuses README's safe-alias mechanism; no regression
# ---------------------------------------------------------------------------

def test_next_steps_does_not_imply_nextjs():
    mentions = find_concept_mentions("Discuss next steps with the hiring manager")
    assert "framework.nextjs" not in [m.concept_id for m in mentions]


def test_ordinary_go_does_not_imply_language_go():
    mentions = find_concept_mentions("We go above and beyond for our customers")
    assert "language.go" not in [m.concept_id for m in mentions]


def test_explicit_golang_form_does_resolve():
    mentions = find_concept_mentions("Experience with Golang is required")
    assert [m.concept_id for m in mentions] == ["language.go"]


def test_uses_nextjs_resolves_correctly():
    mentions = find_concept_mentions("Experience with Next.js required")
    assert [m.concept_id for m in mentions] == ["framework.nextjs"]


def test_bare_js_does_not_fire_from_nextjs_mention():
    mentions = find_concept_mentions("Experience with Next.js required")
    assert "language.javascript" not in [m.concept_id for m in mentions]


def test_independent_javascript_mention_still_resolves():
    mentions = find_concept_mentions("Strong JavaScript and TypeScript skills")
    assert {m.concept_id for m in mentions} == {"language.javascript", "language.typescript"}


# ---------------------------------------------------------------------------
# Conservative unknown-technical-term policy (Part 5)
# ---------------------------------------------------------------------------

def test_unknown_term_co_listed_with_known_concept_is_preserved():
    mentions = find_concept_mentions("Experience with Python, Kubernetes, and Docker")
    unknown = find_conservative_unknown_terms("Experience with Python, Kubernetes, and Docker", mentions)
    assert unknown == ("Kubernetes",)


def test_isolated_unknown_term_with_no_confirming_context_is_not_promoted():
    mentions = find_concept_mentions("Strong communication skills")
    unknown = find_conservative_unknown_terms("Strong communication skills", mentions)
    assert unknown == ()


def test_ordinary_prose_never_produces_unknown_concepts():
    text = "We value excellent communication and a strong work ethic"
    mentions = find_concept_mentions(text)
    assert find_conservative_unknown_terms(text, mentions) == ()


# ---------------------------------------------------------------------------
# Alternatives / OR (Part 14) -- CRITICAL: OR must never become AND
# ---------------------------------------------------------------------------

def test_python_or_go_contains_alternative_marker():
    assert contains_alternative_marker("Python or Go")


def test_aws_or_azure_contains_alternative_marker():
    assert contains_alternative_marker("Experience with AWS or Azure")


def test_plain_and_list_does_not_contain_alternative_marker():
    assert not contains_alternative_marker("Experience with Python, PostgreSQL, and Docker")


def test_no_alternative_marker_in_simple_requirement():
    assert not contains_alternative_marker("Experience with React")


# ---------------------------------------------------------------------------
# Milestone 6B.1: classify_alternative_claim -- structured alternative groups
# ---------------------------------------------------------------------------

def test_python_or_go_is_a_fully_resolved_technical_alternative():
    result = classify_alternative_claim("Python or Go")
    assert result.kind == "technical"
    assert result.concept_ids == ("language.go", "language.python")


def test_go_or_python_is_the_same_set_as_python_or_go():
    a = classify_alternative_claim("Python or Go")
    b = classify_alternative_claim("Go or Python")
    assert a.concept_ids == b.concept_ids


def test_aws_or_azure_is_a_mixed_resolved_and_unresolved_alternative():
    result = classify_alternative_claim("Experience with AWS or Azure")
    assert result.kind == "technical"
    assert result.concept_ids == ("cloud.aws", "unresolved:azure")


def test_postgresql_mysql_or_mongodb_is_a_three_way_alternative():
    result = classify_alternative_claim("Experience with PostgreSQL, MySQL, or MongoDB")
    assert result.kind == "technical"
    assert result.concept_ids == ("database.postgresql", "unresolved:mongodb", "unresolved:mysql")


def test_react_and_typescript_is_not_technical_alternative_kind():
    # No standalone "or" at all -- must be handled as plain conjunction,
    # not routed through alternative-group logic.
    result = classify_alternative_claim("React and TypeScript")
    assert result.kind == "not_technical"


def test_python_postgresql_and_docker_is_not_technical_alternative_kind():
    result = classify_alternative_claim("Python, PostgreSQL, and Docker")
    assert result.kind == "not_technical"


def test_degree_or_related_field_is_not_a_technical_alternative():
    # No confirmed concept anywhere in the OR-list -- must not manufacture
    # a fake technical alternative group out of ordinary HR boilerplate.
    result = classify_alternative_claim("Bachelor's degree in Computer Science or related field")
    assert result.kind == "not_technical"


def test_experience_or_equivalent_education_is_not_a_technical_alternative():
    result = classify_alternative_claim("3+ years experience or equivalent education")
    assert result.kind == "not_technical"


def test_mixed_unsafe_alternative_falls_back_to_unsafe_kind():
    # "Python" confirms technical context, but "a genuinely amazing
    # attitude" fails the conservative shape check -- must not silently
    # drop it or recklessly invent an unresolved id for it.
    result = classify_alternative_claim("Python or a genuinely amazing attitude")
    assert result.kind == "unsafe"
    assert result.concept_ids == ()


def test_single_confirmed_concept_with_no_second_option_is_unsafe():
    # Degenerate case: both sides resolve to the SAME concept, leaving
    # fewer than two distinct options -- not a genuine alternative group.
    result = classify_alternative_claim("Python or python")
    assert result.kind == "unsafe"


def test_trailing_necessity_wording_does_not_pollute_the_alternative_name():
    result = classify_alternative_claim("Python or Go required")
    assert result.concept_ids == ("language.go", "language.python")


def test_trailing_filler_wording_does_not_pollute_the_alternative_name():
    result = classify_alternative_claim("Python or Go experience")
    assert result.concept_ids == ("language.go", "language.python")


def test_no_or_marker_at_all_is_not_technical_kind():
    result = classify_alternative_claim("Experience with React")
    assert result.kind == "not_technical"
    assert result.concept_ids == ()


# ---------------------------------------------------------------------------
# Necessity inference (Part 7)
# ---------------------------------------------------------------------------

def test_must_have_infers_required():
    assert infer_necessity("must have Python experience", Necessity.PREFERRED) == Necessity.REQUIRED


def test_experience_required_infers_required():
    assert infer_necessity("Python experience required", Necessity.PREFERRED) == Necessity.REQUIRED


def test_is_preferred_infers_preferred():
    assert infer_necessity("experience with CUDA is preferred", Necessity.REQUIRED) == Necessity.PREFERRED


def test_is_a_plus_infers_preferred():
    assert infer_necessity("ROS2 is a plus", Necessity.REQUIRED) == Necessity.PREFERRED


def test_nice_to_have_inline_infers_preferred():
    assert infer_necessity("nice to have: Kubernetes", Necessity.REQUIRED) == Necessity.PREFERRED


def test_no_local_wording_falls_back_to_section_hint():
    assert infer_necessity("Experience with Python", Necessity.PREFERRED) == Necessity.PREFERRED
    assert infer_necessity("Experience with Python", Necessity.REQUIRED) == Necessity.REQUIRED


def test_local_wording_overrides_section_hint():
    # Section says PREFERRED, but the sentence itself says required.
    assert infer_necessity("Kubernetes experience is required", Necessity.PREFERRED) == Necessity.REQUIRED


# ---------------------------------------------------------------------------
# Importance inference (Part 8)
# ---------------------------------------------------------------------------

def test_importance_defaults_to_medium():
    assert infer_importance("Experience with Python", Necessity.REQUIRED) == Importance.MEDIUM


def test_importance_high_on_strong_wording():
    assert infer_importance("Expert-level Python required", Necessity.REQUIRED) == Importance.HIGH


def test_importance_low_on_hedge_wording():
    assert infer_importance("Familiarity with Docker", Necessity.REQUIRED) == Importance.LOW


def test_preferred_necessity_defaults_to_low_importance():
    assert infer_importance("Experience with AWS", Necessity.PREFERRED) == Importance.LOW


def test_no_floating_point_weights():
    result = infer_importance("Experience with Python", Necessity.REQUIRED)
    assert isinstance(result, Importance)
    assert not isinstance(result, float)


# ---------------------------------------------------------------------------
# GitHub observability policy (Part 9) -- centralized, data-driven
# ---------------------------------------------------------------------------

def test_technical_requirements_default_strongly_observable():
    assert observability_for_technical() == GithubObservability.STRONGLY_OBSERVABLE


def test_professional_experience_not_observable():
    assert observability_for_non_technical("experience") == GithubObservability.NOT_OBSERVABLE


def test_communication_not_observable():
    assert observability_for_non_technical("soft_skill") == GithubObservability.NOT_OBSERVABLE


def test_degree_not_observable():
    assert observability_for_non_technical("education") == GithubObservability.NOT_OBSERVABLE


def test_leadership_is_partially_observable():
    assert observability_for_non_technical("leadership") == GithubObservability.PARTIALLY_OBSERVABLE


def test_unrecognized_non_technical_category_defaults_to_not_observable():
    assert observability_for_non_technical("some_new_category") == GithubObservability.NOT_OBSERVABLE
    assert observability_for_non_technical(None) == GithubObservability.NOT_OBSERVABLE


# ---------------------------------------------------------------------------
# Parser confidence (Part 12) -- distinct meaning from evidence confidence
# ---------------------------------------------------------------------------

def test_resolved_concept_is_high_confidence():
    assert confidence_for("resolved_concept") == ParserConfidence.HIGH


def test_alternative_fallback_is_low_confidence():
    assert confidence_for("alternative_fallback") == ParserConfidence.LOW


def test_unresolved_listed_term_is_medium_confidence():
    assert confidence_for("unresolved_concept_listed") == ParserConfidence.MEDIUM


def test_experience_qualifier_is_high_confidence():
    assert confidence_for("experience_qualifier") == ParserConfidence.HIGH


# ---------------------------------------------------------------------------
# Non-technical requirement recognition (Part 10)
# ---------------------------------------------------------------------------

def test_bachelors_degree_is_education_category():
    result = find_non_technical_match("Bachelor's degree in Computer Science required")
    assert result is not None
    assert result[0] == "education"


def test_work_authorization_is_legal_category():
    result = find_non_technical_match("Must be eligible to work in Canada")
    assert result is not None
    assert result[0] == "legal"


def test_communication_skills_is_soft_skill_category():
    result = find_non_technical_match("Excellent written and verbal communication skills")
    assert result is not None
    assert result[0] == "soft_skill"


def test_mentoring_is_leadership_category():
    result = find_non_technical_match("Experience mentoring junior engineers")
    assert result is not None
    assert result[0] == "leadership"


def test_no_non_technical_match_for_a_plain_technical_claim():
    assert find_non_technical_match("Experience with Python") is None


# ---------------------------------------------------------------------------
# Experience qualifiers (Part 15)
# ---------------------------------------------------------------------------

def test_explicit_years_experience_detected():
    assert find_experience_qualifier("3+ years of Python experience") is not None


def test_years_without_the_word_experience_still_detected():
    assert find_experience_qualifier("2+ years working with Kubernetes") is not None


def test_no_experience_qualifier_in_plain_requirement():
    assert find_experience_qualifier("Experience with Docker") is None


# ---------------------------------------------------------------------------
# Deduplication (Part 13)
# ---------------------------------------------------------------------------

def _req(text, concept_id=None, necessity=Necessity.REQUIRED, importance=Importance.MEDIUM, category=None, span=None):
    return JobRequirement(
        original_text=text,
        necessity=necessity,
        importance=importance,
        github_observability=GithubObservability.STRONGLY_OBSERVABLE if concept_id else GithubObservability.NOT_OBSERVABLE,
        concept_id=concept_id,
        category=category,
        source_span=span,
    )


def _alt_req(text, alternative_concept_ids, necessity=Necessity.REQUIRED, importance=Importance.MEDIUM):
    return JobRequirement(
        original_text=text,
        necessity=necessity,
        importance=importance,
        github_observability=GithubObservability.STRONGLY_OBSERVABLE,
        alternative_concept_ids=alternative_concept_ids,
    )


def test_python_or_go_and_go_or_python_dedupe_to_one_alternative_group():
    # Milestone 6B.1: reordered alternatives are the SAME logical
    # requirement -- tuple ordering must not accidentally change identity.
    a = _alt_req("Python or Go", ("language.python", "language.go"))
    b = _alt_req("Go or Python", ("language.go", "language.python"))
    result = deduplicate_requirements([a, b])
    assert len(result) == 1


def test_different_alternative_groups_are_not_duplicates():
    python_or_go = _alt_req("Python or Go", ("language.python", "language.go"))
    aws_or_azure = _alt_req("AWS or Azure", ("cloud.aws", "unresolved:azure"))
    result = deduplicate_requirements([python_or_go, aws_or_azure])
    assert len(result) == 2


def test_same_alternative_set_different_necessity_are_not_duplicates():
    required = _alt_req("Python or Go", ("language.python", "language.go"), necessity=Necessity.REQUIRED)
    preferred = _alt_req("Python or Go preferred", ("language.python", "language.go"), necessity=Necessity.PREFERRED)
    result = deduplicate_requirements([required, preferred])
    assert len(result) == 2


def test_alternative_group_never_collides_with_a_single_concept_requirement():
    # Regression guard for the bug this milestone's dedup fix addresses:
    # is_technical is True for BOTH single-concept and alternative-group
    # requirements, so the dedup key must not collapse them just because
    # concept_id is None for both.
    single = _req("Python required", concept_id="language.python")
    group = _alt_req("Python or Go", ("language.python", "language.go"))
    result = deduplicate_requirements([single, group])
    assert len(result) == 2


def test_repeated_identical_technical_requirement_collapses_to_one():
    r1 = _req("Strong Python skills", concept_id="language.python", span=SourceSpan(0, 20))
    r2 = _req("Build Python backend services", concept_id="language.python", span=SourceSpan(50, 80))
    result = deduplicate_requirements([r1, r2])
    assert len(result) == 1
    assert result[0].concept_id == "language.python"


def test_same_concept_different_necessity_are_not_duplicates():
    r1 = _req("Python required", concept_id="language.python", necessity=Necessity.REQUIRED)
    r2 = _req("Python nice to have elsewhere", concept_id="language.python", necessity=Necessity.PREFERRED)
    result = deduplicate_requirements([r1, r2])
    assert len(result) == 2


def test_technical_and_experience_claims_from_overlapping_text_both_survive():
    # "Python required" and "5 years professional Python experience" --
    # overlapping technical concept, but materially different claims.
    technical_1 = _req("Python required", concept_id="language.python")
    technical_2 = _req("5 years professional Python experience", concept_id="language.python")
    experience = _req(
        "5 years professional Python experience", concept_id=None, category="experience"
    )
    result = deduplicate_requirements([technical_1, technical_2, experience])
    # The two technical Python claims collapse (same fact, restated).
    concept_rows = [r for r in result if r.is_technical]
    assert len(concept_rows) == 1
    # But the experience claim is NEVER lost.
    experience_rows = [r for r in result if r.category == "experience"]
    assert len(experience_rows) == 1


def test_non_technical_requirements_with_different_text_are_not_duplicates():
    r1 = _req("3+ years professional experience", category="experience")
    r2 = _req("5 years professional experience preferred", category="experience", necessity=Necessity.PREFERRED)
    result = deduplicate_requirements([r1, r2])
    assert len(result) == 2


def test_dedup_keeps_the_higher_importance_occurrence():
    weak = _req("Familiarity with Python", concept_id="language.python", importance=Importance.LOW)
    strong = _req("Expert-level Python required", concept_id="language.python", importance=Importance.HIGH)
    result = deduplicate_requirements([weak, strong])
    assert len(result) == 1
    assert result[0].importance == Importance.HIGH


def test_dedup_preserves_first_occurrence_order():
    a = _req("A", concept_id="language.python")
    b = _req("B", concept_id="database.postgresql")
    c = _req("C", concept_id="infra.docker")
    result = deduplicate_requirements([a, b, c])
    assert [r.original_text for r in result] == ["A", "B", "C"]


def test_empty_input_produces_empty_output():
    assert deduplicate_requirements([]) == ()
