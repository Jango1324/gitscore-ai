"""Milestone 8A -- the API's own request/response contract.

These Pydantic models are the STABLE, API-facing shape -- deliberately
NOT a dump of any domain dataclass (`JobAnalysisResult`, `JobAssessment`,
`RequirementMatch`, `Evidence`, ...). The API package selects what a
frontend needs and nothing else; see `gitscore.api.serialization` for
the one place that converts domain objects into these models.

Transport-level validation lives here (non-empty, maximum length) --
NOT semantic validation of job-description content, which stays out of
the HTTP layer entirely (`gitscore.jobs.parse_job_description()` already
owns that).
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

# GitHub's own account-name limit (a real platform fact, not invented
# here) -- https://docs.github.com/.../username limits usernames to 39
# characters.
GITHUB_USERNAME_MAX_LENGTH = 39

# Generous enough for any real pasted job posting, small enough that a
# single request body can't be used to send megabytes of arbitrary text
# through the parser.
JOB_DESCRIPTION_MAX_LENGTH = 20_000

JOB_TITLE_MAX_LENGTH = 200
JOB_COMPANY_MAX_LENGTH = 200


class AnalyzeRequest(BaseModel):
    """`POST /api/v1/analyze` request body.

    Only `github_username`/`job_description` are required -- the
    internal knobs `analyze_job_fit()` also accepts (`top_n`, a custom
    `GitHubClient`, ...) are deliberately NOT exposed on the public API
    (Milestone 8A Part 4).
    """

    github_username: str = Field(min_length=1, max_length=GITHUB_USERNAME_MAX_LENGTH)
    job_description: str = Field(min_length=1, max_length=JOB_DESCRIPTION_MAX_LENGTH)
    job_title: str | None = Field(default=None, max_length=JOB_TITLE_MAX_LENGTH)
    job_company: str | None = Field(default=None, max_length=JOB_COMPANY_MAX_LENGTH)

    @field_validator("github_username", "job_description")
    @classmethod
    def _required_field_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty/whitespace-only")
        return stripped

    @field_validator("job_title", "job_company")
    @classmethod
    def _optional_field_blank_becomes_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class RepositoryIdentityOut(BaseModel):
    owner: str
    name: str


class EvidenceOut(BaseModel):
    """One provenance-backed observation, API-facing.

    Only fields `gitscore.evidence.models.Evidence` actually stores are
    serialized here -- no repository URL (the domain model deliberately
    has no `source_url` field; see its docstring) and no `location`
    (no extractor populates it yet, so there is nothing real to expose).
    `detail` is `Evidence.raw_observation` -- a short, already-bounded
    snippet (extractors cap this; never a full README/manifest dump).
    """

    concept_id: str
    evidence_type: str
    confidence: str
    repository: RepositoryIdentityOut
    file_path: str | None
    detail: str


class RequirementOut(BaseModel):
    """One `RequirementMatch`, API-facing.

    `status` uses the existing neutral `MatchStatus` values
    ("supported" / "not_observed" / "not_assessable") -- never
    "failed"/"missing_skill"/"unqualified" (Milestone 8A Part 9/10: a
    7A/7B product-semantics requirement, not a new decision made here).

    `category` (Milestone 9C, additive) is the raw passthrough of
    `JobRequirement.category` -- present for transparency/debugging, not
    itself the field a frontend should branch its presentation on.

    `interpretation_status` (Milestone 9C, additive) is the ONE new
    DERIVED field a frontend should actually use: "recognized" (the
    requirement has a structured, GitHub-observable concept mapping --
    covers both `supported` and `not_observed`, and a `not_assessable`
    requirement can never be "recognized"), "non_technical" (a genuine
    `not_assessable` claim GitHub evidence cannot speak to at all --
    education/experience/legal/soft-skill/leadership, or the Milestone
    6B.1 "unsafe" alternative-group fallback), or "unparsed_placeholder"
    (a `not_assessable` requirement that is GitScore's OWN parser
    uncertainty -- the Milestone 9A non-fabricating placeholder,
    `category in {"unresolved_requirement", "alternative_requirement"}`).
    Computed ONCE, server-side (`gitscore.api.serialization`), so this
    classification rule lives in exactly one tested place -- never
    duplicated in frontend TypeScript. Introduces NO new `MatchStatus`:
    `status` is unchanged; this is a presentation-only refinement of
    WHY a `not_assessable` status was reached.
    """

    text: str
    status: str
    necessity: str
    importance: str
    github_observability: str
    parser_confidence: str | None
    concept_id: str | None
    category: str | None
    interpretation_status: str
    alternative_concept_ids: list[str]
    matched_concept_ids: list[str]
    evidence: list[EvidenceOut]


class SubscoreOut(BaseModel):
    supported: int
    assessable: int


class AnalysisMetaOut(BaseModel):
    github_username: str
    job_title: str | None
    job_company: str | None


class AssessmentOut(BaseModel):
    """`uninterpreted_requirement_count` (Milestone 9C, additive) is the
    count of `not_assessable` requirements whose
    `interpretation_status == "unparsed_placeholder"` (GitScore's OWN
    parser uncertainty, never a genuinely non-technical claim).
    Informational only: never read by, and never affects,
    `github_evidence_alignment` or `assessable_requirement_count` --
    those two fields and the underlying formula are byte-for-byte
    unchanged by this milestone.
    """

    github_evidence_alignment: int | None
    assessable_requirement_count: int
    uninterpreted_requirement_count: int


class RepositoryAnalysisOut(BaseModel):
    discovered: int
    analyzed: int
    partially_analyzed: int
    complete: bool


class RequirementGroupsOut(BaseModel):
    supported: list[RequirementOut]
    not_observed: list[RequirementOut]
    not_assessable: list[RequirementOut]


class DiagnosticsOut(BaseModel):
    extraction_failure_count: int
    unknown_dependency_count: int


class UnparsedClaimOut(BaseModel):
    """Milestone 9C, additive -- one claim the parser's segmentation
    step judged requirement-shaped for which NO `JobRequirement` was
    ever produced at all (see `gitscore.jobs.parsing.parser.UnparsedClaim`'s
    own docstring). Deliberately just the raw original text -- there is
    no status, concept, necessity, or observability to attach, because
    nothing downstream of segmentation ever saw this claim.
    """

    text: str


class VersionsOut(BaseModel):
    matcher: str
    scoring: str
    job_parser: str
    evidence_schema: int


class AnalyzeResponse(BaseModel):
    """`POST /api/v1/analyze` response body.

    `required`/`preferred` are `SubscoreOut | None` -- `None` (JSON
    `null`) when `JobAssessment.required`/`.preferred` is `None` (no
    assessable requirement of that necessity tier exists), NEVER
    fabricated as `SubscoreOut(supported=0, assessable=0)` (Milestone 8A
    Part 11 / the domain's own distinction -- see
    `assessment.models.SubscoreFacts`'s docstring). Same for
    `assessment.github_evidence_alignment` (Part 12): `None` stays
    `null`, never coerced to `0`/`"N/A"`/`-1`.

    `unparsed_claims` (Milestone 9C, additive) is usually empty -- it is
    populated only for the claims `UnparsedClaimOut` itself describes
    (segmentation judged them requirement-shaped; nothing downstream
    produced a row). It is a SEPARATE list from `requirements.*`
    entirely -- never merged into `not_assessable`, which still only
    ever contains real `RequirementOut` rows.
    """

    analysis: AnalysisMetaOut
    assessment: AssessmentOut
    required: SubscoreOut | None
    preferred: SubscoreOut | None
    repository_analysis: RepositoryAnalysisOut
    requirements: RequirementGroupsOut
    unparsed_claims: list[UnparsedClaimOut]
    diagnostics: DiagnosticsOut
    versions: VersionsOut


class HealthResponse(BaseModel):
    status: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool


class ErrorResponse(BaseModel):
    """The one structured error shape every non-2xx response uses."""

    error: ErrorDetail
