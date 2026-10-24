"""Milestone 8A -- domain objects -> API response models.

The ONE place a `JobAnalysisResult` (and everything reachable from it)
is converted into the stable, API-facing shape defined in
`gitscore.api.schemas`. Pure functions only -- no GitHub calls, no
re-matching, no re-assessment; every value here is read directly off an
already-computed domain object, never recomputed (mirroring the "derive,
never duplicate" discipline `JobAssessment`/`JobMatchAnalysis` themselves
already apply).
"""
from __future__ import annotations

from gitscore.api.schemas import (
    AnalysisMetaOut,
    AnalyzeResponse,
    AssessmentOut,
    DiagnosticsOut,
    EvidenceOut,
    RepositoryAnalysisOut,
    RepositoryIdentityOut,
    RequirementGroupsOut,
    RequirementOut,
    SubscoreOut,
    UnparsedClaimOut,
    VersionsOut,
)
from gitscore.application.job_fit import JobAnalysisResult
from gitscore.assessment.models import SubscoreFacts
from gitscore.evidence.models import Evidence, RepositoryIdentity
from gitscore.jobs.parsing.parser import UnparsedClaim
from gitscore.matching.models import RequirementMatch
from gitscore.matching.types import MatchStatus

# Milestone 9C -- the ONE place the "is this NOT_ASSESSABLE requirement
# GitScore's OWN parser uncertainty, or a genuinely non-technical claim"
# classification rule lives (see RequirementOut.interpretation_status's
# docstring). Both category values are Milestone 9A's own non-
# fabricating placeholders (`category="unresolved_requirement"` -- the
# last-resort fallback in `jobs.parsing.parser`; `category=
# "alternative_requirement"` -- the Milestone 6B.1 "unsafe" OR-group
# fallback) -- never a real non_technical.py phrase-table category.
_UNPARSED_PLACEHOLDER_CATEGORIES = frozenset({"unresolved_requirement", "alternative_requirement"})


def _interpretation_status(match: RequirementMatch) -> str:
    """"recognized" (status != NOT_ASSESSABLE -- the requirement had a
    structured, GitHub-observable concept mapping the matcher could
    evaluate, whether SUPPORTED or NOT_OBSERVED), "unparsed_placeholder"
    (NOT_ASSESSABLE because GitScore's own parser could not confidently
    interpret the claim), or "non_technical" (NOT_ASSESSABLE because the
    claim genuinely is not the kind of thing GitHub evidence can speak
    to at all -- education, experience, legal, soft skills, leadership,
    ...). Introduces no new `MatchStatus`; purely a presentation-layer
    refinement of WHY `NOT_ASSESSABLE` was reached, computed directly
    from fields the domain model already carries.
    """
    if match.status != MatchStatus.NOT_ASSESSABLE:
        return "recognized"
    if match.requirement.category in _UNPARSED_PLACEHOLDER_CATEGORIES:
        return "unparsed_placeholder"
    return "non_technical"


def _enum_name(value) -> str:
    """Lower-cased `.name` for an ordinal (`IntEnum`) domain enum --
    `Importance`/`GithubObservability`/`ParserConfidence`/
    `ConfidenceLevel`. Never the raw underlying int: a bare `1`/`2`/`3`
    in JSON would be an unreadable implementation detail a frontend
    would have to look up against this codebase to interpret.
    """
    return value.name.lower()


def serialize_repository_identity(identity: RepositoryIdentity) -> RepositoryIdentityOut:
    return RepositoryIdentityOut(owner=identity.owner, name=identity.name)


def serialize_evidence(evidence: Evidence) -> EvidenceOut:
    return EvidenceOut(
        concept_id=evidence.concept_id,
        evidence_type=evidence.evidence_type.value,
        confidence=_enum_name(evidence.confidence),
        repository=serialize_repository_identity(evidence.repository),
        file_path=evidence.file_path,
        detail=evidence.raw_observation,
    )


def serialize_requirement_match(match: RequirementMatch) -> RequirementOut:
    requirement = match.requirement
    return RequirementOut(
        text=requirement.original_text,
        status=match.status.value,
        necessity=requirement.necessity.value,
        importance=_enum_name(requirement.importance),
        github_observability=_enum_name(requirement.github_observability),
        parser_confidence=(
            _enum_name(requirement.parser_confidence) if requirement.parser_confidence is not None else None
        ),
        concept_id=requirement.concept_id,
        category=requirement.category,
        interpretation_status=_interpretation_status(match),
        alternative_concept_ids=list(requirement.alternative_concept_ids),
        matched_concept_ids=list(match.matched_concept_ids),
        evidence=[serialize_evidence(item) for item in match.supporting_evidence],
    )


def serialize_unparsed_claim(claim: UnparsedClaim) -> UnparsedClaimOut:
    return UnparsedClaimOut(text=claim.text)


def serialize_subscore(facts: SubscoreFacts | None) -> SubscoreOut | None:
    """`None` stays `None` -- never fabricated as `SubscoreOut(0, 0)`
    (see `AnalyzeResponse`'s own docstring for why those are different
    facts)."""
    if facts is None:
        return None
    return SubscoreOut(supported=facts.supported, assessable=facts.assessable)


def serialize_job_analysis_result(result: JobAnalysisResult) -> AnalyzeResponse:
    assessment = result.assessment
    match_analysis = assessment.match_analysis
    coverage = match_analysis.coverage

    not_assessable = [serialize_requirement_match(m) for m in assessment.not_assessable_matches()]
    uninterpreted_count = sum(1 for r in not_assessable if r.interpretation_status == "unparsed_placeholder")

    return AnalyzeResponse(
        analysis=AnalysisMetaOut(
            github_username=result.candidate_profile.candidate,
            job_title=match_analysis.job_title,
            job_company=match_analysis.job_company,
        ),
        assessment=AssessmentOut(
            github_evidence_alignment=assessment.alignment_score,
            assessable_requirement_count=assessment.assessable_count,
            uninterpreted_requirement_count=uninterpreted_count,
        ),
        required=serialize_subscore(assessment.required),
        preferred=serialize_subscore(assessment.preferred),
        repository_analysis=RepositoryAnalysisOut(
            discovered=coverage.discovered_count,
            analyzed=coverage.analyzed_count,
            partially_analyzed=coverage.partially_analyzed_count,
            complete=coverage.is_complete,
        ),
        requirements=RequirementGroupsOut(
            supported=[serialize_requirement_match(m) for m in assessment.supported_matches()],
            not_observed=[serialize_requirement_match(m) for m in assessment.not_observed_matches()],
            not_assessable=not_assessable,
        ),
        unparsed_claims=[serialize_unparsed_claim(c) for c in result.unparsed_claims],
        diagnostics=DiagnosticsOut(
            extraction_failure_count=len(result.extractor_failures),
            unknown_dependency_count=len(result.unknown_dependency_names),
        ),
        versions=VersionsOut(
            matcher=match_analysis.matcher_version,
            scoring=assessment.scoring_version,
            job_parser=result.job_profile.parser_version,
            evidence_schema=result.candidate_profile.evidence_schema_version,
        ),
    )
