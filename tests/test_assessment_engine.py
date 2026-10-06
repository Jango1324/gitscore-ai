"""Milestone 7B -- gitscore.assessment (assess_job, JobAssessment,
SubscoreFacts, GitHub Evidence Alignment).

Deterministic, offline, no network calls -- every candidate profile and
job requirement here is hand-constructed, exactly like Milestone 7A's
own `test_matching_engine.py`. This file never calls `match_job()`/
`match_requirement()` indirectly through anything but the real matcher
-- `assess_job()` itself is tested as a pure function of an
already-built `JobMatchAnalysis`, per
`docs/design/MILESTONE_7B_SCORING_DESIGN.md`.
"""
from __future__ import annotations

import dataclasses

import pytest

from gitscore.assessment import SCORING_VERSION, JobAssessment, SubscoreFacts, assess_job
from gitscore.evidence import (
    ConfidenceLevel,
    Evidence,
    EvidenceType,
    RepositoryIdentity,
    build_candidate_evidence_profile,
)
from gitscore.jobs import GithubObservability, Importance, JobRequirement, JobRequirementProfile, Necessity, ParserConfidence
from gitscore.matching import MatchStatus, match_job

REQUIRED = Necessity.REQUIRED
PREFERRED = Necessity.PREFERRED
STRONG_OBS = GithubObservability.STRONGLY_OBSERVABLE
NOT_OBS = GithubObservability.NOT_OBSERVABLE


def repo(name: str, owner: str = "candidate") -> RepositoryIdentity:
    return RepositoryIdentity(owner=owner, name=name)


def ev(
    repo_name: str,
    concept: str,
    *,
    owner: str = "candidate",
    confidence: ConfidenceLevel = ConfidenceLevel.MODERATE,
) -> Evidence:
    return Evidence(
        repository=repo(repo_name, owner),
        evidence_type=EvidenceType.DEPENDENCY,
        raw_observation="observation",
        concept_id=concept,
        confidence=confidence,
        extractor_version="test@1",
    )


def candidate_profile(evidence_items=(), discovered=None, analyzed=None):
    evidence_items = tuple(evidence_items)
    if discovered is None:
        discovered = sorted({item.repository for item in evidence_items}, key=lambda r: (r.owner, r.name))
    if analyzed is None:
        analyzed = discovered
    return build_candidate_evidence_profile(
        "candidate", discovered=discovered, analyzed=analyzed, evidence_items=evidence_items
    )


def requirement(
    text: str,
    *,
    necessity: Necessity = REQUIRED,
    importance: Importance = Importance.MEDIUM,
    observability: GithubObservability = STRONG_OBS,
    concept_id: str | None = None,
    alternative_concept_ids: tuple[str, ...] = (),
    category: str | None = None,
    parser_confidence: ParserConfidence | None = None,
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


def job_profile(requirements) -> JobRequirementProfile:
    return JobRequirementProfile(
        raw_text="placeholder job text long enough to hold spans",
        requirements=tuple(requirements),
        parser_version="manual:v1",
    )


def assessment_for(requirements, evidence_items=()) -> JobAssessment:
    profile = candidate_profile(evidence_items)
    analysis = match_job(profile, job_profile(requirements))
    return assess_job(analysis)


# ---------------------------------------------------------------------------
# Formula correctness / denominator exclusion of NOT_ASSESSABLE
# ---------------------------------------------------------------------------

def test_not_assessable_excluded_from_denominator():
    # 1 supported technical requirement + 2 NOT_ASSESSABLE non-technical
    # claims. A denominator that counted NOT_ASSESSABLE would read 1/3;
    # the correct assessable denominator is 1/1.
    reqs = [
        requirement("Python required", concept_id="language.python"),
        requirement("3+ years experience", observability=NOT_OBS, category="experience"),
        requirement("Bachelor's degree", observability=NOT_OBS, category="education"),
    ]
    assessment = assessment_for(reqs, [ev("repo-a", "language.python")])
    assert assessment.assessable_count == 1
    assert assessment.alignment_score == 100


def test_formula_matches_hand_computed_fraction():
    # 3 supported, 1 not observed -> 3/4 assessable -> 75.
    reqs = [
        requirement("Python", concept_id="language.python"),
        requirement("PostgreSQL", concept_id="database.postgresql"),
        requirement("Docker", concept_id="infra.docker"),
        requirement("AWS", concept_id="cloud.aws"),
    ]
    assessment = assessment_for(
        reqs,
        [
            ev("repo-a", "language.python"),
            ev("repo-a", "database.postgresql"),
            ev("repo-a", "infra.docker"),
        ],
    )
    assert assessment.assessable_count == 4
    assert assessment.alignment_score == 75


# ---------------------------------------------------------------------------
# None / 0 / 100 scores
# ---------------------------------------------------------------------------

def test_no_assessable_requirements_gives_none_not_zero():
    reqs = [
        requirement("3+ years experience", observability=NOT_OBS, category="experience"),
        requirement("Bachelor's degree", observability=NOT_OBS, category="education"),
    ]
    assessment = assessment_for(reqs)
    assert assessment.assessable_count == 0
    assert assessment.alignment_score is None
    assert assessment.required is None
    assert assessment.preferred is None
    assert assessment.low_parser_confidence_count == 0


def test_all_requirements_not_assessable_gives_none():
    reqs = [requirement("Work authorization", observability=NOT_OBS, category="legal")]
    assessment = assessment_for(reqs)
    assert assessment.alignment_score is None


def test_zero_supported_gives_zero():
    reqs = [
        requirement("Python", concept_id="language.python"),
        requirement("PostgreSQL", concept_id="database.postgresql"),
    ]
    assessment = assessment_for(reqs)  # no evidence at all
    assert assessment.assessable_count == 2
    assert assessment.alignment_score == 0


def test_all_supported_gives_hundred():
    reqs = [
        requirement("Python", concept_id="language.python"),
        requirement("PostgreSQL", concept_id="database.postgresql"),
    ]
    assessment = assessment_for(
        reqs, [ev("repo-a", "language.python"), ev("repo-a", "database.postgresql")]
    )
    assert assessment.alignment_score == 100


# ---------------------------------------------------------------------------
# Conventional half-up rounding (not Python's banker's rounding)
# ---------------------------------------------------------------------------

def test_half_up_rounding_62_5_rounds_up_to_63():
    # 5 of 8 assessable supported -> 500/8 = 62.5 -> half-up -> 63.
    # Python's round(62.5) would give 62 (round-half-to-even); this must
    # NOT happen here.
    reqs = [requirement(f"Concept {i}", concept_id=f"unresolved:c{i}") for i in range(8)]
    supported_evidence = [ev(f"repo-{i}", f"unresolved:c{i}") for i in range(5)]
    assessment = assessment_for(reqs, supported_evidence)
    assert assessment.assessable_count == 8
    assert assessment.alignment_score == 63
    assert round(62.5) == 62  # documents why this test exists at all


def test_half_up_rounding_72_5_rounds_up_to_73():
    # 29 of 40 assessable supported -> 2900/40 = 72.5 -> half-up -> 73.
    reqs = [requirement(f"Concept {i}", concept_id=f"unresolved:c{i}") for i in range(40)]
    supported_evidence = [ev(f"repo-{i}", f"unresolved:c{i}") for i in range(29)]
    assessment = assessment_for(reqs, supported_evidence)
    assert assessment.assessable_count == 40
    assert assessment.alignment_score == 73
    assert round(72.5) == 72  # documents the banker's-rounding mismatch


# ---------------------------------------------------------------------------
# Required / preferred SubscoreFacts
# ---------------------------------------------------------------------------

def test_required_and_preferred_subscores_computed_independently():
    reqs = [
        requirement("Python", necessity=REQUIRED, concept_id="language.python"),
        requirement("PostgreSQL", necessity=REQUIRED, concept_id="database.postgresql"),
        requirement("Docker", necessity=PREFERRED, concept_id="infra.docker"),
    ]
    assessment = assessment_for(
        reqs, [ev("repo-a", "language.python"), ev("repo-a", "infra.docker")]
    )
    assert assessment.required == SubscoreFacts(supported=1, assessable=2)
    assert assessment.preferred == SubscoreFacts(supported=1, assessable=1)


def test_only_preferred_assessable_required_is_none():
    reqs = [
        requirement("Work authorization", necessity=REQUIRED, observability=NOT_OBS, category="legal"),
        requirement("Docker", necessity=PREFERRED, concept_id="infra.docker"),
    ]
    assessment = assessment_for(reqs, [ev("repo-a", "infra.docker")])
    assert assessment.required is None
    assert assessment.preferred == SubscoreFacts(supported=1, assessable=1)


def test_only_required_assessable_preferred_is_none():
    reqs = [
        requirement("Python", necessity=REQUIRED, concept_id="language.python"),
        requirement("Nice bonus skill", necessity=PREFERRED, observability=NOT_OBS, category="soft_skill"),
    ]
    assessment = assessment_for(reqs, [ev("repo-a", "language.python")])
    assert assessment.preferred is None
    assert assessment.required == SubscoreFacts(supported=1, assessable=1)


# ---------------------------------------------------------------------------
# The Part 12 adversarial case -- pinned exactly
# ---------------------------------------------------------------------------

def test_adversarial_case_strong_headline_despite_zero_required_support():
    """Required: Python, PostgreSQL both NOT_OBSERVED. Preferred: Docker,
    AWS, React, Redis, GitHub Actions, Kubernetes all SUPPORTED.

    This is Milestone 7B.0's Part 9/12 adversarial example, pinned
    exactly as approved: alignment_score MUST be 75 (unweighted,
    6-of-8), and required MUST independently show 0-of-2. Do NOT "fix"
    this test by capping the score to something lower -- the entire
    point of the approved design is that the headline number is NOT
    secretly discounted; the required subscore is what contextualizes
    it. See docs/design/MILESTONE_7B_SCORING_DESIGN.md Parts 4/9/12 for
    the full rationale a future developer should read before touching
    this test.
    """
    reqs = [
        requirement("Python", necessity=REQUIRED, concept_id="language.python"),
        requirement("PostgreSQL", necessity=REQUIRED, concept_id="database.postgresql"),
        requirement("Docker", necessity=PREFERRED, concept_id="infra.docker"),
        requirement("AWS", necessity=PREFERRED, concept_id="cloud.aws"),
        requirement("React", necessity=PREFERRED, concept_id="unresolved:react"),
        requirement("Redis", necessity=PREFERRED, concept_id="database.redis"),
        requirement("GitHub Actions", necessity=PREFERRED, concept_id="unresolved:github_actions"),
        requirement("Kubernetes", necessity=PREFERRED, concept_id="unresolved:kubernetes"),
    ]
    preferred_evidence = [
        ev("infra-repo", "infra.docker"),
        ev("infra-repo", "cloud.aws"),
        ev("frontend-repo", "unresolved:react"),
        ev("infra-repo", "database.redis"),
        ev("infra-repo", "unresolved:github_actions"),
        ev("infra-repo", "unresolved:kubernetes"),
    ]
    assessment = assessment_for(reqs, preferred_evidence)

    assert assessment.alignment_score == 75
    assert assessment.required == SubscoreFacts(supported=0, assessable=2)
    assert assessment.preferred == SubscoreFacts(supported=6, assessable=6)
    # Not a cap, not a discount -- 75 stands uncapped.
    assert assessment.alignment_score != 20


# ---------------------------------------------------------------------------
# Necessity / Importance / ParserConfidence / evidence-confidence
# independence from the score
# ---------------------------------------------------------------------------

def test_necessity_does_not_change_alignment_score():
    # Same evidence, same statuses, only necessity differs between two
    # otherwise-identical job profiles -> identical alignment_score.
    def reqs_with(necessity):
        return [
            requirement("Python", necessity=necessity, concept_id="language.python"),
            requirement("PostgreSQL", necessity=necessity, concept_id="database.postgresql"),
        ]

    evidence = [ev("repo-a", "language.python")]
    required_assessment = assessment_for(reqs_with(REQUIRED), evidence)
    preferred_assessment = assessment_for(reqs_with(PREFERRED), evidence)
    assert required_assessment.alignment_score == preferred_assessment.alignment_score == 50


def test_importance_does_not_change_alignment_score():
    def reqs_with(importance):
        return [requirement("Python", importance=importance, concept_id="language.python")]

    low = assessment_for(reqs_with(Importance.LOW))
    high = assessment_for(reqs_with(Importance.HIGH))
    assert low.alignment_score == high.alignment_score == 0


def test_parser_confidence_does_not_change_alignment_score():
    def reqs_with(confidence):
        return [
            requirement("Python", concept_id="language.python", parser_confidence=confidence)
        ]

    low = assessment_for(reqs_with(ParserConfidence.LOW), [ev("repo-a", "language.python")])
    high = assessment_for(reqs_with(ParserConfidence.HIGH), [ev("repo-a", "language.python")])
    assert low.alignment_score == high.alignment_score == 100


def test_evidence_confidence_does_not_change_alignment_score():
    reqs = [requirement("Python", concept_id="language.python")]
    weak = assessment_for(reqs, [ev("repo-a", "language.python", confidence=ConfidenceLevel.WEAK)])
    strong = assessment_for(reqs, [ev("repo-a", "language.python", confidence=ConfidenceLevel.STRONG)])
    assert weak.alignment_score == strong.alignment_score == 100


def test_coverage_completeness_does_not_change_alignment_score():
    reqs = [requirement("Python", concept_id="language.python")]
    profile_complete = candidate_profile([ev("repo-a", "language.python")])
    profile_partial = build_candidate_evidence_profile(
        "candidate",
        discovered=[repo("repo-a"), repo("repo-b")],
        analyzed=[repo("repo-a")],
        evidence_items=[ev("repo-a", "language.python")],
    )
    complete = assess_job(match_job(profile_complete, job_profile(reqs)))
    partial = assess_job(match_job(profile_partial, job_profile(reqs)))
    assert complete.alignment_score == partial.alignment_score == 100
    assert complete.match_analysis.coverage.is_complete is True
    assert partial.match_analysis.coverage.is_complete is False


# ---------------------------------------------------------------------------
# low_parser_confidence_count
# ---------------------------------------------------------------------------

def test_low_parser_confidence_counted_among_assessable_requirements():
    reqs = [
        requirement("Python", concept_id="language.python", parser_confidence=ParserConfidence.LOW),
        requirement("PostgreSQL", concept_id="database.postgresql", parser_confidence=ParserConfidence.HIGH),
    ]
    assessment = assessment_for(reqs, [ev("repo-a", "language.python")])
    assert assessment.low_parser_confidence_count == 1


def test_low_parser_confidence_on_not_assessable_requirement_not_counted():
    # LOW-confidence parse of a NOT_ASSESSABLE (non-technical) claim must
    # NOT increment the count -- it is scoped to assessable requirements
    # only (docs/design/MILESTONE_7B_SCORING_DESIGN.md Part 6 / Edge Case J).
    reqs = [
        requirement(
            "Some ambiguous soft-skill phrase",
            observability=NOT_OBS,
            category="soft_skill",
            parser_confidence=ParserConfidence.LOW,
        ),
        requirement("Python", concept_id="language.python", parser_confidence=ParserConfidence.HIGH),
    ]
    assessment = assessment_for(reqs, [ev("repo-a", "language.python")])
    assert assessment.low_parser_confidence_count == 0


def test_none_parser_confidence_not_counted_as_low():
    reqs = [requirement("Python", concept_id="language.python", parser_confidence=None)]
    assessment = assessment_for(reqs)
    assert assessment.low_parser_confidence_count == 0


# ---------------------------------------------------------------------------
# OR groups count once; unresolved concepts get no special treatment
# ---------------------------------------------------------------------------

def test_or_group_counts_as_exactly_one_assessable_requirement():
    # Milestone 8D.1: a deliberately synthetic, guaranteed-unregistered
    # term (Kubernetes is now a registered concept) to keep demonstrating
    # this section's "unresolved concepts get no special treatment" claim
    # with an ACTUALLY-unresolved concept id.
    reqs = [
        requirement(
            "Docker or SomeUnknownOrchestrator",
            concept_id=None,
            alternative_concept_ids=("infra.docker", "unresolved:someunknownorchestrator"),
        )
    ]
    assessment = assessment_for(reqs, [ev("repo-a", "infra.docker")])
    assert assessment.assessable_count == 1
    assert assessment.alignment_score == 100


def test_unresolved_concept_requirement_scored_like_any_other():
    reqs = [requirement("Some brand-new framework", concept_id="unresolved:newframework")]
    assessment = assessment_for(reqs, [ev("repo-a", "unresolved:newframework")])
    assert assessment.alignment_score == 100


# ---------------------------------------------------------------------------
# Candidate with zero evidence
# ---------------------------------------------------------------------------

def test_candidate_with_zero_evidence_everything_not_observed():
    reqs = [
        requirement("Python", concept_id="language.python"),
        requirement("PostgreSQL", necessity=PREFERRED, concept_id="database.postgresql"),
    ]
    assessment = assessment_for(reqs)
    assert assessment.alignment_score == 0
    assert assessment.required == SubscoreFacts(supported=0, assessable=1)
    assert assessment.preferred == SubscoreFacts(supported=0, assessable=1)
    assert len(assessment.not_observed_matches()) == 2
    assert assessment.supported_matches() == ()


# ---------------------------------------------------------------------------
# Grouping helpers: no copying/rebuilding, deterministic order preserved
# ---------------------------------------------------------------------------

def test_grouping_helpers_preserve_order_and_identity():
    reqs = [
        requirement("Python", concept_id="language.python"),
        requirement("3+ years experience", observability=NOT_OBS, category="experience"),
        requirement("PostgreSQL", concept_id="database.postgresql"),
    ]
    profile = candidate_profile([ev("repo-a", "language.python")])
    analysis = match_job(profile, job_profile(reqs))
    assessment = assess_job(analysis)

    supported = assessment.supported_matches()
    not_observed = assessment.not_observed_matches()
    not_assessable = assessment.not_assessable_matches()

    assert [m.requirement.original_text for m in supported] == ["Python"]
    assert [m.requirement.original_text for m in not_observed] == ["PostgreSQL"]
    assert [m.requirement.original_text for m in not_assessable] == ["3+ years experience"]

    # Grouping helpers return the SAME RequirementMatch objects already
    # on match_analysis.requirement_matches -- never copies/rebuilds.
    assert supported[0] is analysis.requirement_matches[0]
    assert not_observed[0] is analysis.requirement_matches[2]
    assert not_assessable[0] is analysis.requirement_matches[1]


# ---------------------------------------------------------------------------
# Determinism / purity of assess_job
# ---------------------------------------------------------------------------

def test_assess_job_is_pure_and_deterministic():
    reqs = [requirement("Python", concept_id="language.python")]
    profile = candidate_profile([ev("repo-a", "language.python")])
    analysis = match_job(profile, job_profile(reqs))

    first = assess_job(analysis)
    second = assess_job(analysis)
    assert first.alignment_score == second.alignment_score == 100
    assert first.match_analysis is analysis
    assert first.scoring_version == second.scoring_version == SCORING_VERSION


def test_assess_job_performs_no_rematching():
    # assess_job never touches candidate/job profiles -- it only reads
    # the already-computed JobMatchAnalysis's RequirementMatch tuple.
    reqs = [requirement("Python", concept_id="language.python")]
    profile = candidate_profile([ev("repo-a", "language.python")])
    analysis = match_job(profile, job_profile(reqs))
    assessment = assess_job(analysis)
    assert assessment.match_analysis.requirement_matches is analysis.requirement_matches


# ---------------------------------------------------------------------------
# SubscoreFacts invariants
# ---------------------------------------------------------------------------

def test_subscore_facts_rejects_zero_assessable():
    with pytest.raises(ValueError):
        SubscoreFacts(supported=0, assessable=0)


def test_subscore_facts_rejects_negative_supported():
    with pytest.raises(ValueError):
        SubscoreFacts(supported=-1, assessable=2)


def test_subscore_facts_rejects_supported_exceeding_assessable():
    with pytest.raises(ValueError):
        SubscoreFacts(supported=3, assessable=2)


def test_subscore_facts_accepts_zero_supported_nonzero_assessable():
    facts = SubscoreFacts(supported=0, assessable=2)
    assert facts.supported == 0
    assert facts.assessable == 2


def test_subscore_facts_is_frozen():
    facts = SubscoreFacts(supported=1, assessable=2)
    with pytest.raises(dataclasses.FrozenInstanceError):
        facts.supported = 2  # type: ignore[misc]


# ---------------------------------------------------------------------------
# JobAssessment invariants
# ---------------------------------------------------------------------------

def test_job_assessment_rejects_empty_scoring_version():
    profile = candidate_profile([])
    analysis = match_job(profile, job_profile([requirement("Python", concept_id="language.python")]))
    with pytest.raises(ValueError):
        JobAssessment(match_analysis=analysis, scoring_version="   ")


def test_alignment_score_none_iff_assessable_count_zero():
    not_assessable_only = assessment_for(
        [requirement("Work authorization", observability=NOT_OBS, category="legal")]
    )
    assert not_assessable_only.assessable_count == 0
    assert not_assessable_only.alignment_score is None

    has_assessable = assessment_for([requirement("Python", concept_id="language.python")])
    assert has_assessable.assessable_count > 0
    assert has_assessable.alignment_score is not None


def test_alignment_score_bounds():
    for supported_count in range(0, 4):
        reqs = [requirement(f"Concept {i}", concept_id=f"unresolved:c{i}") for i in range(3)]
        evidence = [ev(f"repo-{i}", f"unresolved:c{i}") for i in range(min(supported_count, 3))]
        score = assessment_for(reqs, evidence).alignment_score
        assert score is not None
        assert 0 <= score <= 100


def test_low_parser_confidence_count_never_exceeds_assessable_count():
    reqs = [
        requirement(f"Concept {i}", concept_id=f"unresolved:c{i}", parser_confidence=ParserConfidence.LOW)
        for i in range(3)
    ]
    assessment = assessment_for(reqs)
    assert assessment.low_parser_confidence_count <= assessment.assessable_count


# ---------------------------------------------------------------------------
# No generated prose anywhere in the domain objects
# ---------------------------------------------------------------------------

def test_job_assessment_has_no_prose_or_presentation_fields():
    assessment = assessment_for([requirement("Python", concept_id="language.python")])
    field_names = {f.name for f in dataclasses.fields(assessment)}
    assert field_names == {"match_analysis", "scoring_version"}
    assert not hasattr(assessment, "explanation")
    assert not hasattr(assessment, "summary")
    assert not hasattr(assessment, "coverage_note")
    assert not hasattr(assessment, "coverage_percentage")
    assert not hasattr(assessment, "hire_recommendation")
