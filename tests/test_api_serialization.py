"""Milestone 8A -- `gitscore.api.serialization` domain -> API conversion.

Pure, offline, no GitHub/HTTP involved: a hand-built `JobAnalysisResult`
(mirroring `tests/test_assessment_manual_examples.py`'s own
hand-constructed `Evidence`/`CandidateEvidenceProfile` pattern) run
through `serialize_job_analysis_result()`, asserting exact JSON-facing
values. This is what makes serialization independently testable without
spinning up the FastAPI app at all.
"""
from __future__ import annotations

from gitscore.api.schemas import SubscoreOut
from gitscore.api.serialization import serialize_job_analysis_result
from gitscore.application import JobAnalysisResult
from gitscore.assessment import assess_job
from gitscore.evidence import ConfidenceLevel, Evidence, EvidenceType, RepositoryIdentity, build_candidate_evidence_profile
from gitscore.jobs import parse_job_description
from gitscore.matching import match_job
from gitscore.pipeline.evidence import ExtractionFailure

BACKEND_JD = """Backend Software Engineer

Requirements:
- 3+ years of experience building Python backend services
- Experience with PostgreSQL
- Familiarity with Docker
- Excellent written and verbal communication

Preferred Qualifications:
- Experience with AWS
- Experience with Next.js
"""

ML_JD = """Machine Learning Engineer

Requirements:
- Expert-level Python
- Deep experience with PyTorch
- 5+ years of professional software engineering experience
- Experience with Docker or Kubernetes

Preferred Qualifications:
- Experience deploying models to AWS or Azure
"""

ZERO_ASSESSABLE_JD = """Requirements:
- 3+ years of professional experience required
- Bachelor degree in Computer Science required
- Excellent communication and leadership skills
"""


def repo(name: str, owner: str = "candidate") -> RepositoryIdentity:
    return RepositoryIdentity(owner=owner, name=name)


def ev(repo_name: str, concept: str, evidence_type=EvidenceType.DEPENDENCY, confidence=ConfidenceLevel.MODERATE, file_path=None) -> Evidence:
    return Evidence(
        repository=repo(repo_name),
        evidence_type=evidence_type,
        raw_observation=f"observation for {concept}",
        concept_id=concept,
        confidence=confidence,
        extractor_version="test@1",
        file_path=file_path,
    )


def build_result(raw_text, title, evidence_items, *, extractor_failures=(), unknown_dependency_names=()):
    evidence_items = tuple(evidence_items)
    repos = sorted({item.repository for item in evidence_items}, key=lambda r: (r.owner, r.name))
    candidate_profile = build_candidate_evidence_profile(
        "octocat", discovered=repos, analyzed=repos, evidence_items=evidence_items
    )
    job_profile = parse_job_description(raw_text, title=title)
    match_analysis = match_job(candidate_profile, job_profile)
    assessment = assess_job(match_analysis)
    return JobAnalysisResult(
        candidate_profile=candidate_profile,
        job_profile=job_profile,
        assessment=assessment,
        extractor_failures=tuple(extractor_failures),
        unknown_dependency_names=tuple(unknown_dependency_names),
    )


# ---------------------------------------------------------------------------
# Happy path -- exact values
# ---------------------------------------------------------------------------


def test_happy_path_serializes_exact_values():
    result = build_result(
        BACKEND_JD,
        "Backend Software Engineer",
        [
            ev("api-service", "language.python", EvidenceType.REPOSITORY_LANGUAGE, ConfidenceLevel.STRONG),
            ev("api-service", "infra.docker", EvidenceType.DOCKER, ConfidenceLevel.STRONG, file_path="Dockerfile"),
        ],
    )

    response = serialize_job_analysis_result(result)

    assert response.analysis.github_username == "octocat"
    assert response.analysis.job_title == "Backend Software Engineer"
    assert response.analysis.job_company is None

    assert response.assessment.github_evidence_alignment == 40
    assert response.assessment.assessable_requirement_count == 5
    assert response.required == SubscoreOut(supported=2, assessable=3)
    assert response.preferred == SubscoreOut(supported=0, assessable=2)

    assert response.repository_analysis.discovered == 1
    assert response.repository_analysis.analyzed == 1
    assert response.repository_analysis.partially_analyzed == 0
    assert response.repository_analysis.complete is True

    supported_texts = {r.text for r in response.requirements.supported}
    assert any("Docker" in t for t in supported_texts)
    assert len(response.requirements.supported) == 2
    assert len(response.requirements.not_observed) == 3  # postgresql, aws, next.js


# ---------------------------------------------------------------------------
# D/E/F: None stays None (never 0/"N/A"/-1, never SubscoreOut(0, 0))
# ---------------------------------------------------------------------------


def test_zero_assessable_requirements_alignment_is_none():
    result = build_result(ZERO_ASSESSABLE_JD, None, [])

    response = serialize_job_analysis_result(result)

    assert response.assessment.github_evidence_alignment is None
    assert response.assessment.assessable_requirement_count == 0
    assert response.required is None
    assert response.preferred is None


def test_only_required_assessable_preferred_is_none():
    # BACKEND_JD's required tier (python/postgresql/docker) is always
    # assessable; isolate a posting where preferred has nothing assessable
    # by using one with no preferred technical claims at all.
    only_required_jd = """Requirements:
- Experience with Docker
- Experience with PostgreSQL
"""
    result = build_result(only_required_jd, None, [ev("api-service", "infra.docker", EvidenceType.DOCKER)])

    response = serialize_job_analysis_result(result)

    assert response.required is not None
    assert response.preferred is None


# ---------------------------------------------------------------------------
# G/H: NOT_OBSERVED / NOT_ASSESSABLE preserved with neutral status values
# ---------------------------------------------------------------------------


def test_not_observed_and_not_assessable_use_neutral_status_values():
    result = build_result(BACKEND_JD, "Backend Software Engineer", [])

    response = serialize_job_analysis_result(result)

    not_observed_statuses = {r.status for r in response.requirements.not_observed}
    not_assessable_statuses = {r.status for r in response.requirements.not_assessable}
    assert not_observed_statuses == {"not_observed"}
    assert not_assessable_statuses == {"not_assessable"}
    # Never rendered as a verdict about the candidate.
    forbidden = {"failed", "missing_skill", "unqualified", "gap"}
    all_statuses = {r.status for group in (
        response.requirements.supported, response.requirements.not_observed, response.requirements.not_assessable
    ) for r in group}
    assert all_statuses.isdisjoint(forbidden)

    # NOT_ASSESSABLE requirements are present in the response, not omitted.
    not_assessable_texts = {r.text for r in response.requirements.not_assessable}
    assert any("communication" in t.lower() for t in not_assessable_texts)
    assert any("experience" in t.lower() for t in not_assessable_texts)


# ---------------------------------------------------------------------------
# I: OR-group alternative/matched concept ids preserved
# ---------------------------------------------------------------------------


def test_or_group_concept_ids_preserved():
    result = build_result(
        ML_JD,
        "Machine Learning Engineer",
        [ev("training-repo", "infra.docker", EvidenceType.DOCKER, ConfidenceLevel.STRONG)],
    )

    response = serialize_job_analysis_result(result)

    or_group = next(r for r in response.requirements.supported if len(r.alternative_concept_ids) > 1)
    assert or_group.concept_id is None
    assert or_group.alternative_concept_ids == ["infra.docker", "unresolved:kubernetes"]
    assert or_group.matched_concept_ids == ["infra.docker"]


# ---------------------------------------------------------------------------
# J: supporting evidence serialized faithfully
# ---------------------------------------------------------------------------


def test_evidence_shape_reflects_only_real_domain_fields():
    result = build_result(
        BACKEND_JD,
        "Backend Software Engineer",
        [ev("api-service", "infra.docker", EvidenceType.DOCKER, ConfidenceLevel.STRONG, file_path="Dockerfile")],
    )

    response = serialize_job_analysis_result(result)

    docker_match = next(r for r in response.requirements.supported if r.concept_id == "infra.docker")
    assert len(docker_match.evidence) == 1
    item = docker_match.evidence[0]
    assert item.concept_id == "infra.docker"
    assert item.evidence_type == "docker"
    assert item.confidence == "strong"
    assert item.repository.owner == "candidate"
    assert item.repository.name == "api-service"
    assert item.file_path == "Dockerfile"
    assert item.detail == "observation for infra.docker"
    # No fabricated repository URL -- RepositoryIdentity has no such field.
    assert not hasattr(item.repository, "url")


def test_supported_requirement_with_no_evidence_is_impossible_by_construction():
    # RequirementMatch itself forbids SUPPORTED with empty evidence
    # (matching/models.py's own __post_init__) -- nothing to test here
    # beyond confirming NOT_OBSERVED/NOT_ASSESSABLE always serialize an
    # empty evidence list, never null.
    result = build_result(BACKEND_JD, "Backend Software Engineer", [])
    response = serialize_job_analysis_result(result)
    for group in (response.requirements.not_observed, response.requirements.not_assessable):
        for requirement in group:
            assert requirement.evidence == []


# ---------------------------------------------------------------------------
# K: diagnostics preserved
# ---------------------------------------------------------------------------


def test_diagnostics_counts_preserved():
    failure = ExtractionFailure(repository=repo("flaky"), source="languages", error="boom")
    result = build_result(
        BACKEND_JD,
        "Backend Software Engineer",
        [],
        extractor_failures=(failure,),
        unknown_dependency_names=("some-made-up-thing",),
    )

    response = serialize_job_analysis_result(result)

    assert response.diagnostics.extraction_failure_count == 1
    assert response.diagnostics.unknown_dependency_count == 1


# ---------------------------------------------------------------------------
# Versions -- read straight off the domain objects, never re-derived
# ---------------------------------------------------------------------------


def test_versions_match_domain_objects_exactly():
    result = build_result(BACKEND_JD, "Backend Software Engineer", [])

    response = serialize_job_analysis_result(result)

    assert response.versions.matcher == result.assessment.match_analysis.matcher_version
    assert response.versions.scoring == result.assessment.scoring_version
    assert response.versions.job_parser == result.job_profile.parser_version
    assert response.versions.evidence_schema == result.candidate_profile.evidence_schema_version


# ---------------------------------------------------------------------------
# Enum serialization -- readable strings, never raw ordinals
# ---------------------------------------------------------------------------


def test_ordinal_enums_serialize_as_lowercase_names_not_raw_ints():
    result = build_result(BACKEND_JD, "Backend Software Engineer", [])

    response = serialize_job_analysis_result(result)

    all_requirements = (
        response.requirements.supported + response.requirements.not_observed + response.requirements.not_assessable
    )
    for requirement in all_requirements:
        assert requirement.importance in {"low", "medium", "high"}
        assert requirement.github_observability in {"not_observable", "partially_observable", "strongly_observable"}
        assert requirement.necessity in {"required", "preferred"}
        if requirement.parser_confidence is not None:
            assert requirement.parser_confidence in {"low", "medium", "high"}
        assert requirement.status in {"supported", "not_observed", "not_assessable"}
