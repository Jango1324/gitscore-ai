"""Milestone 7A -- gitscore.matching (match_requirement, match_job,
RequirementMatch, JobMatchAnalysis, MatchStatus, evidence-support policy).

Deterministic, offline, no network calls -- every candidate profile and
job requirement here is hand-constructed, exactly like Milestone 6A/6B's
own domain-model tests.
"""
import dataclasses

import pytest

from gitscore.concepts import unresolved_concept_id
from gitscore.evidence import (
    ConfidenceLevel,
    Evidence,
    EvidenceType,
    RepositoryIdentity,
    build_candidate_evidence_profile,
)
from gitscore.jobs import GithubObservability, Importance, JobRequirement, JobRequirementProfile, Necessity
from gitscore.matching import (
    MATCHER_VERSION,
    MINIMUM_SUPPORTING_CONFIDENCE,
    JobMatchAnalysis,
    MatchStatus,
    RequirementMatch,
    has_sufficient_evidence,
    match_job,
    match_requirement,
)

REQUIRED = Necessity.REQUIRED
PREFERRED = Necessity.PREFERRED
STRONG_OBS = GithubObservability.STRONGLY_OBSERVABLE
WEAK_OBS = GithubObservability.PARTIALLY_OBSERVABLE
NOT_OBS = GithubObservability.NOT_OBSERVABLE


def repo(name: str, owner: str = "candidate") -> RepositoryIdentity:
    return RepositoryIdentity(owner=owner, name=name)


def ev(
    repo_name: str,
    concept: str,
    *,
    owner: str = "candidate",
    obs: str = "observation",
    confidence: ConfidenceLevel = ConfidenceLevel.MODERATE,
    evidence_type: EvidenceType = EvidenceType.DEPENDENCY,
    file_path: str | None = None,
) -> Evidence:
    return Evidence(
        repository=repo(repo_name, owner),
        evidence_type=evidence_type,
        raw_observation=obs,
        concept_id=concept,
        confidence=confidence,
        extractor_version="test@1",
        file_path=file_path,
    )


def candidate_profile(evidence_items=(), discovered=None, analyzed=None, partially_analyzed=()):
    evidence_items = tuple(evidence_items)
    if discovered is None:
        discovered = sorted({item.repository for item in evidence_items}, key=lambda r: (r.owner, r.name))
    if analyzed is None:
        analyzed = discovered
    return build_candidate_evidence_profile(
        "candidate",
        discovered=discovered,
        analyzed=analyzed,
        evidence_items=evidence_items,
        partially_analyzed=partially_analyzed,
    )


def requirement(
    text: str = "Python required",
    *,
    necessity: Necessity = REQUIRED,
    importance: Importance = Importance.HIGH,
    observability: GithubObservability = STRONG_OBS,
    concept_id: str | None = "language.python",
    alternative_concept_ids: tuple[str, ...] = (),
    category: str | None = None,
    parser_confidence=None,
) -> JobRequirement:
    return JobRequirement(
        original_text=text,
        necessity=necessity,
        importance=importance,
        github_observability=observability,
        concept_id=concept_id,
        alternative_concept_ids=alternative_concept_ids,
        category=category,
        parser_confidence=parser_confidence,
    )


def job_profile(requirements, title=None) -> JobRequirementProfile:
    return JobRequirementProfile(
        raw_text="placeholder job text long enough to hold spans",
        requirements=tuple(requirements),
        parser_version="manual:v1",
        title=title,
    )


# ---------------------------------------------------------------------------
# A/B -- normal resolved requirement, with and without evidence
# ---------------------------------------------------------------------------

def test_a_normal_requirement_supported_with_evidence():
    profile = candidate_profile([ev("backend", "language.python")])
    req = requirement(concept_id="language.python")
    match = match_requirement(req, profile)
    assert match.status == MatchStatus.SUPPORTED
    assert match.matched_concept_ids == ("language.python",)
    assert len(match.supporting_evidence) == 1


def test_b_normal_requirement_not_observed_without_evidence():
    profile = candidate_profile([ev("backend", "database.postgresql")])
    req = requirement(concept_id="language.python")
    match = match_requirement(req, profile)
    assert match.status == MatchStatus.NOT_OBSERVED
    assert match.matched_concept_ids == ()
    assert match.supporting_evidence == ()


# ---------------------------------------------------------------------------
# C/D/E/F -- OR (alternative_concept_ids) requirements
# ---------------------------------------------------------------------------

def _python_or_go():
    return requirement(
        "Python or Go",
        concept_id=None,
        alternative_concept_ids=("language.python", "language.go"),
    )


def test_c_or_requirement_first_alternative_supported():
    profile = candidate_profile([ev("r1", "language.python")])
    match = match_requirement(_python_or_go(), profile)
    assert match.status == MatchStatus.SUPPORTED
    assert match.matched_concept_ids == ("language.python",)


def test_d_or_requirement_second_alternative_supported():
    profile = candidate_profile([ev("r1", "language.go")])
    match = match_requirement(_python_or_go(), profile)
    assert match.status == MatchStatus.SUPPORTED
    assert match.matched_concept_ids == ("language.go",)


def test_e_or_requirement_both_supported_deterministic():
    profile = candidate_profile([ev("r1", "language.python"), ev("r1", "language.go")])
    match = match_requirement(_python_or_go(), profile)
    assert match.status == MatchStatus.SUPPORTED
    assert match.matched_concept_ids == ("language.go", "language.python")  # sorted
    assert len(match.supporting_evidence) == 2
    # Deterministic regardless of how many times it's recomputed.
    match_again = match_requirement(_python_or_go(), profile)
    assert match_again.matched_concept_ids == match.matched_concept_ids


def test_f_or_requirement_neither_supported():
    profile = candidate_profile([ev("r1", "database.postgresql")])
    match = match_requirement(_python_or_go(), profile)
    assert match.status == MatchStatus.NOT_OBSERVED


def test_or_requirement_never_becomes_and_even_with_full_evidence():
    # Sanity guard against the exact bug class 6B.1 was built to prevent:
    # the matcher must never require ALL alternatives, only ANY.
    profile = candidate_profile([ev("r1", "language.python")])
    match = match_requirement(_python_or_go(), profile)
    assert match.status == MatchStatus.SUPPORTED


# ---------------------------------------------------------------------------
# G -- AND semantics across two independent requirements
# ---------------------------------------------------------------------------

def test_g_independent_requirements_and_semantics():
    profile = candidate_profile([ev("r1", "language.python")])
    python_req = requirement("Python required", concept_id="language.python")
    postgres_req = requirement("PostgreSQL required", concept_id="database.postgresql")
    analysis = match_job(profile, job_profile([python_req, postgres_req]))
    assert analysis.requirement_matches[0].status == MatchStatus.SUPPORTED
    assert analysis.requirement_matches[1].status == MatchStatus.NOT_OBSERVED


# ---------------------------------------------------------------------------
# H/I/J -- non-observable claims are NOT_ASSESSABLE, never a technical gap
# ---------------------------------------------------------------------------

def test_h_experience_claim_is_not_assessable():
    profile = candidate_profile([])
    req = requirement(
        "3+ years professional experience",
        concept_id=None,
        observability=NOT_OBS,
        category="experience",
    )
    match = match_requirement(req, profile)
    assert match.status == MatchStatus.NOT_ASSESSABLE


def test_i_education_claim_is_not_assessable():
    profile = candidate_profile([])
    req = requirement(
        "Bachelor's degree in Computer Science",
        concept_id=None,
        observability=NOT_OBS,
        category="education",
    )
    assert match_requirement(req, profile).status == MatchStatus.NOT_ASSESSABLE


def test_j_work_authorization_claim_is_not_assessable():
    profile = candidate_profile([])
    req = requirement(
        "Must be eligible to work in the United States",
        concept_id=None,
        observability=NOT_OBS,
        category="legal",
    )
    assert match_requirement(req, profile).status == MatchStatus.NOT_ASSESSABLE


def test_not_observable_wins_even_if_a_concept_id_is_somehow_attached():
    # Defensive: NOT_OBSERVABLE is never second-guessed by a concept
    # mapping happening to be present (not produced by the current
    # parser, but the domain model does not forbid it).
    profile = candidate_profile([ev("r1", "language.python")])
    req = requirement("Weirdly-tagged claim", concept_id="language.python", observability=NOT_OBS)
    assert match_requirement(req, profile).status == MatchStatus.NOT_ASSESSABLE


# ---------------------------------------------------------------------------
# K/L/M -- necessity / importance / parser confidence independence
# ---------------------------------------------------------------------------

def test_k_necessity_does_not_change_evidence_status():
    profile = candidate_profile([ev("r1", "language.python")])
    required = requirement("Python required", necessity=REQUIRED, concept_id="language.python")
    preferred = requirement("Python preferred", necessity=PREFERRED, concept_id="language.python")
    assert match_requirement(required, profile).status == MatchStatus.SUPPORTED
    assert match_requirement(preferred, profile).status == MatchStatus.SUPPORTED


def test_l_importance_does_not_change_evidence_status():
    profile = candidate_profile([])
    high = requirement("Python", importance=Importance.HIGH, concept_id="language.python")
    low = requirement("Python", importance=Importance.LOW, concept_id="language.python")
    assert match_requirement(high, profile).status == MatchStatus.NOT_OBSERVED
    assert match_requirement(low, profile).status == MatchStatus.NOT_OBSERVED


def test_m_parser_confidence_does_not_change_evidence_status():
    from gitscore.jobs import ParserConfidence

    profile = candidate_profile([ev("r1", "language.python")])
    low_conf = requirement("Python", concept_id="language.python", parser_confidence=ParserConfidence.LOW)
    high_conf = requirement("Python", concept_id="language.python", parser_confidence=ParserConfidence.HIGH)
    assert match_requirement(low_conf, profile).status == MatchStatus.SUPPORTED
    assert match_requirement(high_conf, profile).status == MatchStatus.SUPPORTED
    # ParserConfidence is preserved on the requirement for 7B, untouched.
    assert match_requirement(low_conf, profile).requirement.parser_confidence == ParserConfidence.LOW


# ---------------------------------------------------------------------------
# N -- evidence-confidence threshold behavior
# ---------------------------------------------------------------------------

def test_n_weak_confidence_alone_is_sufficient_per_current_policy():
    assert MINIMUM_SUPPORTING_CONFIDENCE == ConfidenceLevel.WEAK
    profile = candidate_profile([ev("r1", "language.python", confidence=ConfidenceLevel.WEAK)])
    match = match_requirement(requirement(concept_id="language.python"), profile)
    assert match.status == MatchStatus.SUPPORTED


def test_n_strongest_evidence_confidence_wins_when_mixed():
    profile = candidate_profile(
        [
            ev("r1", "language.python", confidence=ConfidenceLevel.WEAK),
            ev("r2", "language.python", confidence=ConfidenceLevel.STRONG),
        ]
    )
    summary = profile.concept("language.python")
    assert summary.strongest_confidence == ConfidenceLevel.STRONG
    assert has_sufficient_evidence(summary)


def test_n_has_sufficient_evidence_is_false_for_missing_concept():
    profile = candidate_profile([])
    assert has_sufficient_evidence(profile.concept("language.python")) is False


# ---------------------------------------------------------------------------
# O -- duplicate / multiple supporting evidence retained, not collapsed
# ---------------------------------------------------------------------------

def test_o_multiple_distinct_evidence_items_all_retained():
    profile = candidate_profile(
        [
            ev("r1", "language.python", evidence_type=EvidenceType.DEPENDENCY, obs="requirements.txt: python"),
            ev("r1", "language.python", evidence_type=EvidenceType.REPOSITORY_LANGUAGE, obs="Python: 80%"),
            ev("r2", "language.python", obs="requirements.txt: python"),
        ]
    )
    match = match_requirement(requirement(concept_id="language.python"), profile)
    assert match.status == MatchStatus.SUPPORTED
    assert len(match.supporting_evidence) == 3


# ---------------------------------------------------------------------------
# P -- deterministic ordering
# ---------------------------------------------------------------------------

def test_p_requirement_matches_preserve_job_profile_order():
    profile = candidate_profile([])
    reqs = [
        requirement("Python", concept_id="language.python"),
        requirement("PostgreSQL", concept_id="database.postgresql"),
        requirement("Docker", concept_id="infra.docker"),
    ]
    analysis = match_job(profile, job_profile(reqs))
    assert [m.requirement.original_text for m in analysis.requirement_matches] == [
        "Python",
        "PostgreSQL",
        "Docker",
    ]


def test_p_supporting_evidence_order_is_deterministic_regardless_of_input_order():
    items = [ev("r2", "language.python", obs="b"), ev("r1", "language.python", obs="a")]
    profile_a = candidate_profile(items)
    profile_b = candidate_profile(list(reversed(items)))
    match_a = match_requirement(requirement(concept_id="language.python"), profile_a)
    match_b = match_requirement(requirement(concept_id="language.python"), profile_b)
    assert match_a.supporting_evidence == match_b.supporting_evidence


# ---------------------------------------------------------------------------
# Q -- repository-analysis coverage is preserved, not turned into a score
# ---------------------------------------------------------------------------

def test_q_coverage_is_preserved_on_the_analysis_and_unaffected_by_match_status():
    profile = candidate_profile(
        [ev("r1", "language.python")],
        discovered=[repo("r1"), repo("r2"), repo("r3")],
        analyzed=[repo("r1")],
    )
    analysis = match_job(profile, job_profile([requirement(concept_id="language.python")]))
    assert analysis.coverage.discovered_count == 3
    assert analysis.coverage.analyzed_count == 1
    assert analysis.coverage.is_complete is False
    # Coverage is descriptive only -- it does not change match status.
    assert analysis.requirement_matches[0].status == MatchStatus.SUPPORTED


def test_q_requirement_match_itself_has_no_redundant_coverage_field():
    match = RequirementMatch(requirement=requirement(), status=MatchStatus.NOT_OBSERVED)
    assert not hasattr(match, "coverage")


# ---------------------------------------------------------------------------
# R -- PARTIALLY_OBSERVABLE requirement behavior
# ---------------------------------------------------------------------------

def test_r_partially_observable_with_concept_mapping_is_checked_normally():
    # Mirrors an actual existing fixture shape (Milestone 6A manual
    # examples): "AWS experience preferred" is PARTIALLY_OBSERVABLE but
    # DOES carry a concept_id.
    profile = candidate_profile([ev("r1", "cloud.aws")])
    req = requirement("AWS experience preferred", observability=WEAK_OBS, concept_id="cloud.aws")
    assert match_requirement(req, profile).status == MatchStatus.SUPPORTED


def test_r_partially_observable_with_concept_mapping_and_no_evidence_is_not_observed():
    profile = candidate_profile([])
    req = requirement("AWS experience preferred", observability=WEAK_OBS, concept_id="cloud.aws")
    assert match_requirement(req, profile).status == MatchStatus.NOT_OBSERVED


def test_r_partially_observable_without_concept_mapping_is_not_assessable():
    # Mirrors "leadership" / the 6B.1 unsafe alternative-group fallback:
    # PARTIALLY_OBSERVABLE with no concept_id and no alternative group.
    profile = candidate_profile([])
    req = requirement(
        "Demonstrated technical leadership",
        observability=WEAK_OBS,
        concept_id=None,
        category="leadership",
    )
    assert match_requirement(req, profile).status == MatchStatus.NOT_ASSESSABLE


def test_r_partially_observable_alternative_group_is_checked_normally():
    profile = candidate_profile([ev("r1", "cloud.aws")])
    req = requirement(
        "AWS or Azure",
        observability=WEAK_OBS,
        concept_id=None,
        alternative_concept_ids=("cloud.aws", "unresolved:azure"),
    )
    assert match_requirement(req, profile).status == MatchStatus.SUPPORTED


# ---------------------------------------------------------------------------
# S -- unresolved concept requirements
# ---------------------------------------------------------------------------

def test_s_unresolved_concept_requirement_supported_by_matching_unresolved_evidence():
    # Milestone 8D.1: a deliberately synthetic, guaranteed-unregistered
    # term, rather than a real (if differently-granular) technology name
    # that could itself enter the registry in a future milestone.
    term_id = unresolved_concept_id("SomeUnknownOrchestrator")
    profile = candidate_profile([ev("r1", term_id)])
    req = requirement(f"{term_id} experience", concept_id=term_id)
    match = match_requirement(req, profile)
    assert match.status == MatchStatus.SUPPORTED
    assert match.matched_concept_ids == (term_id,)


def test_s_unresolved_concept_requirement_not_observed_without_matching_evidence():
    term_id = unresolved_concept_id("SomeUnknownOrchestrator")
    profile = candidate_profile([ev("r1", "language.python")])
    req = requirement(f"{term_id} experience", concept_id=term_id)
    assert match_requirement(req, profile).status == MatchStatus.NOT_OBSERVED


# ---------------------------------------------------------------------------
# T -- empty candidate profile
# ---------------------------------------------------------------------------

def test_t_empty_candidate_profile_technical_requirements_all_not_observed():
    profile = candidate_profile([])
    reqs = [
        requirement("Python", concept_id="language.python"),
        requirement("Python or Go", concept_id=None, alternative_concept_ids=("language.python", "language.go")),
    ]
    analysis = match_job(profile, job_profile(reqs))
    assert all(m.status == MatchStatus.NOT_OBSERVED for m in analysis.requirement_matches)


def test_t_empty_candidate_profile_non_technical_requirement_is_not_assessable():
    profile = candidate_profile([])
    req = requirement("5+ years experience", concept_id=None, observability=NOT_OBS, category="experience")
    assert match_requirement(req, profile).status == MatchStatus.NOT_ASSESSABLE


# ---------------------------------------------------------------------------
# U -- empty requirement profile (valid input, not a manufactured invariant)
# ---------------------------------------------------------------------------

def test_u_empty_requirement_profile_produces_empty_analysis():
    profile = candidate_profile([ev("r1", "language.python")])
    empty_job = job_profile([])
    analysis = match_job(profile, empty_job)
    assert analysis.requirement_matches == ()
    assert analysis.requirement_count == 0
    assert analysis.supported_count == 0


# ---------------------------------------------------------------------------
# JobMatchAnalysis: identity, counts, versioning
# ---------------------------------------------------------------------------

def test_job_match_analysis_counts_are_purely_descriptive():
    profile = candidate_profile([ev("r1", "language.python")])
    reqs = [
        requirement("Python", concept_id="language.python"),
        requirement("PostgreSQL", concept_id="database.postgresql"),
        requirement("3+ years experience", concept_id=None, observability=NOT_OBS, category="experience"),
    ]
    analysis = match_job(profile, job_profile(reqs, title="Backend Engineer"))
    assert analysis.supported_count == 1
    assert analysis.not_observed_count == 1
    assert analysis.not_assessable_count == 1
    assert analysis.requirement_count == 3
    assert analysis.job_title == "Backend Engineer"
    assert analysis.candidate == "candidate"


def test_matcher_version_is_stamped():
    profile = candidate_profile([])
    analysis = match_job(profile, job_profile([requirement()]))
    assert analysis.matcher_version == MATCHER_VERSION
    assert isinstance(MATCHER_VERSION, str) and MATCHER_VERSION.strip()


def test_matches_with_status_filters_correctly():
    profile = candidate_profile([ev("r1", "language.python")])
    reqs = [
        requirement("Python", concept_id="language.python"),
        requirement("Go", concept_id="language.go"),
    ]
    analysis = match_job(profile, job_profile(reqs))
    supported = analysis.matches_with_status(MatchStatus.SUPPORTED)
    assert len(supported) == 1
    assert supported[0].requirement.original_text == "Python"


# ---------------------------------------------------------------------------
# RequirementMatch invariants
# ---------------------------------------------------------------------------

def test_supported_status_requires_matched_concept_ids_and_evidence():
    with pytest.raises(ValueError):
        RequirementMatch(requirement=requirement(), status=MatchStatus.SUPPORTED)


def test_supported_status_requires_evidence_even_with_matched_ids():
    with pytest.raises(ValueError):
        RequirementMatch(
            requirement=requirement(),
            status=MatchStatus.SUPPORTED,
            matched_concept_ids=("language.python",),
        )


def test_not_observed_status_rejects_matched_concept_ids():
    profile_evidence = (ev("r1", "language.python"),)
    with pytest.raises(ValueError):
        RequirementMatch(
            requirement=requirement(),
            status=MatchStatus.NOT_OBSERVED,
            matched_concept_ids=("language.python",),
            supporting_evidence=profile_evidence,
        )


def test_matched_concept_ids_must_belong_to_the_requirement():
    with pytest.raises(ValueError):
        RequirementMatch(
            requirement=requirement(concept_id="language.python"),
            status=MatchStatus.SUPPORTED,
            matched_concept_ids=("database.postgresql",),
            supporting_evidence=(ev("r1", "database.postgresql"),),
        )


def test_matched_concept_ids_must_be_sorted():
    req = requirement(
        concept_id=None,
        alternative_concept_ids=("language.go", "language.python"),
    )
    with pytest.raises(ValueError):
        RequirementMatch(
            requirement=req,
            status=MatchStatus.SUPPORTED,
            matched_concept_ids=("language.python", "language.go"),
            supporting_evidence=(ev("r1", "language.python"),),
        )


def test_requirement_match_is_frozen_and_hashable():
    match = RequirementMatch(requirement=requirement(), status=MatchStatus.NOT_OBSERVED)
    with pytest.raises(dataclasses.FrozenInstanceError):
        match.status = MatchStatus.SUPPORTED
    hash(match)  # must not raise


def test_job_match_analysis_rejects_blank_candidate():
    with pytest.raises(ValueError):
        JobMatchAnalysis(
            candidate="   ",
            job_title=None,
            job_company=None,
            requirement_matches=(),
            coverage=candidate_profile([]).coverage,
            matcher_version=MATCHER_VERSION,
        )
