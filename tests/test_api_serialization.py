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
from gitscore.jobs import parse_job_description, parse_job_description_with_diagnostics
from gitscore.matching import match_job
from gitscore.pipeline.evidence import ExtractionFailure

# Milestone 9C -- one claim of each interpretation_status kind, in one
# posting: a recognized technical requirement (Docker), a genuinely
# non-technical claim (communication), GitScore's own two non-fabricating
# placeholder shapes (the bare-lead-in "unresolved_requirement" and the
# Milestone 6B.1 "unsafe" OR-group "alternative_requirement"), and one
# claim that produces ZERO JobRequirement rows at all (an UnparsedClaim).
# Exact behavior verified directly against the real parser before writing
# any assertion below -- never assumed.
MIXED_INTERPRETATION_JD = """Requirements:
- Experience with Docker
- Excellent written and verbal communication
- Experience with Terraform
- Proficiency in Python, Rust, or an equally performant systems language
- Experience designing distributed systems
"""

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
    # Milestone 9C: uses the diagnostics-aware parse so `unparsed_claims`
    # is populated too -- `.profile` is pinned byte-identical to
    # `parse_job_description()`'s own output
    # (tests/test_job_parser_diagnostics.py), so every existing
    # assertion in this file is unaffected.
    parsed = parse_job_description_with_diagnostics(raw_text, title=title)
    job_profile = parsed.profile
    match_analysis = match_job(candidate_profile, job_profile)
    assessment = assess_job(match_analysis)
    return JobAnalysisResult(
        candidate_profile=candidate_profile,
        job_profile=job_profile,
        assessment=assessment,
        extractor_failures=tuple(extractor_failures),
        unknown_dependency_names=tuple(unknown_dependency_names),
        unparsed_claims=parsed.unparsed_claims,
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
    assert or_group.alternative_concept_ids == ["infra.docker", "infra.kubernetes"]
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


# ---------------------------------------------------------------------------
# Milestone 9C -- category / interpretation_status / uninterpreted count /
# unparsed_claims
# ---------------------------------------------------------------------------


def _by_text(items, text):
    return next(r for r in items if r.text == text)


def test_recognized_technical_requirement_gets_recognized_interpretation_status():
    result = build_result(MIXED_INTERPRETATION_JD, None, [])
    response = serialize_job_analysis_result(result)

    docker = _by_text(response.requirements.not_observed, "Experience with Docker")
    assert docker.status == "not_observed"
    assert docker.interpretation_status == "recognized"
    assert docker.category == "infrastructure"


def test_genuinely_non_technical_requirement_gets_non_technical_interpretation_status():
    result = build_result(MIXED_INTERPRETATION_JD, None, [])
    response = serialize_job_analysis_result(result)

    comms = _by_text(response.requirements.not_assessable, "Excellent written and verbal communication")
    assert comms.status == "not_assessable"
    assert comms.interpretation_status == "non_technical"
    assert comms.category == "soft_skill"


def test_bare_lead_in_placeholder_gets_unparsed_placeholder_interpretation_status():
    result = build_result(MIXED_INTERPRETATION_JD, None, [])
    response = serialize_job_analysis_result(result)

    terraform = _by_text(response.requirements.not_assessable, "Experience with Terraform")
    assert terraform.status == "not_assessable"
    assert terraform.interpretation_status == "unparsed_placeholder"
    assert terraform.category == "unresolved_requirement"
    assert terraform.concept_id is None


def test_unsafe_alternative_group_fallback_also_gets_unparsed_placeholder_status():
    """The Milestone 6B.1 'unsafe' OR-group fallback (category=
    'alternative_requirement') is a DIFFERENT parser mechanism from the
    Milestone 9A bare-lead-in placeholder, but both represent the same
    user-facing fact (GitScore could not confidently interpret this
    claim) and so must both classify as 'unparsed_placeholder' -- never
    treated as two different presentation concepts.
    """
    result = build_result(MIXED_INTERPRETATION_JD, None, [])
    response = serialize_job_analysis_result(result)

    unsafe = _by_text(
        response.requirements.not_assessable,
        "Proficiency in Python, Rust, or an equally performant systems language",
    )
    assert unsafe.interpretation_status == "unparsed_placeholder"
    assert unsafe.category == "alternative_requirement"


def test_uninterpreted_requirement_count_counts_only_placeholders_not_genuine_non_technical():
    result = build_result(MIXED_INTERPRETATION_JD, None, [])
    response = serialize_job_analysis_result(result)

    # Terraform + the unsafe OR fallback = 2 placeholders; the
    # communication claim is genuinely non-technical and must NOT be
    # counted here.
    assert response.assessment.uninterpreted_requirement_count == 2


def test_uninterpreted_requirement_count_never_affects_alignment_or_assessable_count():
    """The headline guarantee of this whole milestone: the new count is
    purely informational. Recomputed independently here (not just
    trusted) against the exact same formula `assessment.models` already
    uses, to confirm nothing about the SCORE changed.
    """
    result = build_result(MIXED_INTERPRETATION_JD, None, [])
    response = serialize_job_analysis_result(result)

    assessable = result.assessment.assessable_count
    supported = result.assessment.match_analysis.supported_count
    expected_alignment = round(100 * supported / assessable) if assessable else None

    assert response.assessment.assessable_requirement_count == assessable
    # Docker is the only assessable requirement in this posting (the two
    # placeholders and the non-technical claim are all NOT_ASSESSABLE,
    # excluded from the denominator exactly as before this milestone).
    assert assessable == 1
    assert response.assessment.github_evidence_alignment == expected_alignment


def test_unparsed_claims_serialized_as_a_separate_list_never_merged_into_not_assessable():
    result = build_result(MIXED_INTERPRETATION_JD, None, [])
    response = serialize_job_analysis_result(result)

    assert [c.text for c in response.unparsed_claims] == ["Experience designing distributed systems"]
    # Never duplicated into requirements.not_assessable -- that list only
    # ever contains real RequirementOut rows with a real status.
    not_assessable_texts = {r.text for r in response.requirements.not_assessable}
    assert "Experience designing distributed systems" not in not_assessable_texts


def test_unparsed_claims_is_empty_list_not_omitted_when_there_are_none():
    result = build_result(BACKEND_JD, "Backend Software Engineer", [])
    response = serialize_job_analysis_result(result)
    assert response.unparsed_claims == []


# ---------------------------------------------------------------------------
# Milestone 9E Workstream A -- unparsed_claim_count: a SEPARATE headline
# count from uninterpreted_requirement_count, never double-counting the
# same source claim, never summed into one number.
# ---------------------------------------------------------------------------


def test_unparsed_claim_count_is_zero_when_there_are_no_unparsed_claims():
    result = build_result(BACKEND_JD, "Backend Software Engineer", [])
    response = serialize_job_analysis_result(result)
    assert response.assessment.unparsed_claim_count == 0
    assert response.unparsed_claims == []


def test_unparsed_claim_count_is_one_for_a_single_unparsed_claim():
    # MIXED_INTERPRETATION_JD's "Experience designing distributed systems"
    # is the one claim that survives segmentation but produces zero rows.
    result = build_result(MIXED_INTERPRETATION_JD, None, [])
    response = serialize_job_analysis_result(result)
    assert response.assessment.unparsed_claim_count == 1
    assert [c.text for c in response.unparsed_claims] == ["Experience designing distributed systems"]


def test_unparsed_claim_count_counts_multiple_distinct_claims():
    jd = """Requirements:
- Experience with Docker
- Experience designing distributed systems
- Ability to design and implement scalable backend architectures
"""
    result = build_result(jd, None, [])
    response = serialize_job_analysis_result(result)
    # Two genuinely distinct unparsed claims, both preserved verbatim.
    assert response.assessment.unparsed_claim_count == 2
    assert {c.text for c in response.unparsed_claims} == {
        "Experience designing distributed systems",
        "Ability to design and implement scalable backend architectures",
    }


def test_unparsed_claim_count_never_double_counts_a_duplicated_claim_at_two_source_spans():
    # The SAME unparseable sentence appearing twice at two different
    # source offsets must be counted twice (two real, distinct claims
    # from the posting), never collapsed into one -- unparsed_claims is
    # never deduplicated by text.
    jd = """Requirements:
- Experience designing distributed systems

Preferred Qualifications:
- Experience designing distributed systems
"""
    result = build_result(jd, None, [])
    response = serialize_job_analysis_result(result)
    assert response.assessment.unparsed_claim_count == 2
    assert [c.text for c in response.unparsed_claims] == [
        "Experience designing distributed systems",
        "Experience designing distributed systems",
    ]


def test_unparsed_claim_count_and_uninterpreted_requirement_count_never_overlap():
    # MIXED_INTERPRETATION_JD has exactly 2 unparsed_placeholder rows
    # (Terraform, the unsafe OR fallback) and exactly 1 unparsed_claim
    # ("Experience designing distributed systems") -- a claim is either a
    # real, inspectable row (counted by uninterpreted_requirement_count)
    # or produced zero rows (counted by unparsed_claim_count), never both.
    result = build_result(MIXED_INTERPRETATION_JD, None, [])
    response = serialize_job_analysis_result(result)

    assert response.assessment.uninterpreted_requirement_count == 2
    assert response.assessment.unparsed_claim_count == 1

    placeholder_texts = {
        r.text for r in response.requirements.not_assessable if r.interpretation_status == "unparsed_placeholder"
    }
    unparsed_claim_texts = {c.text for c in response.unparsed_claims}
    assert placeholder_texts.isdisjoint(unparsed_claim_texts)

    # Neither count affects the score.
    assert response.assessment.github_evidence_alignment == result.assessment.alignment_score


def test_unparsed_claim_count_does_not_affect_alignment_or_assessable_count():
    result = build_result(MIXED_INTERPRETATION_JD, None, [])
    response = serialize_job_analysis_result(result)

    assessable = result.assessment.assessable_count
    supported = result.assessment.match_analysis.supported_count
    expected_alignment = round(100 * supported / assessable) if assessable else None

    assert response.assessment.assessable_requirement_count == assessable
    assert response.assessment.github_evidence_alignment == expected_alignment


# ---------------------------------------------------------------------------
# Milestone 9E Workstream B -- concept_label: disambiguating identical
# requirement text across distinct JobRequirement rows.
# ---------------------------------------------------------------------------


def test_concept_label_present_for_a_resolved_technical_requirement():
    result = build_result(MIXED_INTERPRETATION_JD, None, [])
    response = serialize_job_analysis_result(result)

    docker = _by_text(response.requirements.not_observed, "Experience with Docker")
    assert docker.concept_id == "infra.docker"
    assert docker.concept_label == "Docker"


def test_concept_label_is_none_for_non_technical_and_placeholder_requirements():
    result = build_result(MIXED_INTERPRETATION_JD, None, [])
    response = serialize_job_analysis_result(result)

    comms = _by_text(response.requirements.not_assessable, "Excellent written and verbal communication")
    terraform = _by_text(response.requirements.not_assessable, "Experience with Terraform")
    unsafe = _by_text(
        response.requirements.not_assessable,
        "Proficiency in Python, Rust, or an equally performant systems language",
    )

    assert comms.concept_id is None and comms.concept_label is None
    assert terraform.concept_id is None and terraform.concept_label is None
    # An alternative group has no single concept_id either.
    assert unsafe.concept_id is None and unsafe.concept_label is None


def test_concept_label_disambiguates_duplicate_text_rows_from_an_enumeration_list():
    # "Docker and Kubernetes" -> two distinct JobRequirement rows sharing
    # identical original_text, one per matched concept (M9A/6B.1 "one row
    # per concept" design) -- this is the exact M9D-reported duplicate-
    # looking-requirement scenario, disambiguated via concept_label.
    jd = """Requirements:
- Strong experience with Docker and Kubernetes
"""
    result = build_result(jd, None, [ev("infra-repo", "infra.docker", EvidenceType.DOCKER, ConfidenceLevel.STRONG)])
    response = serialize_job_analysis_result(result)

    docker_row = next(r for r in response.requirements.supported if r.concept_id == "infra.docker")
    kubernetes_row = next(r for r in response.requirements.not_observed if r.concept_id == "infra.kubernetes")

    assert docker_row.text == kubernetes_row.text == "Strong experience with Docker and Kubernetes"
    assert docker_row.concept_label == "Docker"
    assert kubernetes_row.concept_label == "Kubernetes"
    assert docker_row.concept_label != kubernetes_row.concept_label


def test_concept_label_for_an_unresolved_concept_in_a_comma_enumeration():
    # "Python, pandas, and numpy" -- numpy has no registry entry, so its
    # row carries an "unresolved:numpy" concept_id; concept_label still
    # renders a readable label rather than the raw id string.
    jd = """Requirements:
- Experience with Python, pandas, and numpy
"""
    result = build_result(jd, None, [])
    response = serialize_job_analysis_result(result)

    numpy_row = next(r for r in response.requirements.not_observed if r.concept_id == "unresolved:numpy")
    assert numpy_row.concept_label == "Numpy"
