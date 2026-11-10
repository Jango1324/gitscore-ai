/**
 * Milestone 8B -- the HTTP contract, as TypeScript types.
 *
 * Hand-written to mirror `gitscore.api.schemas` (Milestone 8A) field for
 * field. These represent the HTTP wire contract only -- never generated
 * from, or coupled to, the Python domain dataclasses behind them. If
 * the backend's JSON shape changes, this file changes; nothing here
 * should be inferred by copying a Python type.
 */

export interface AnalyzeRequest {
  github_username: string;
  job_description: string;
  job_title?: string | null;
  job_company?: string | null;
}

export interface RepositoryIdentity {
  owner: string;
  name: string;
}

export interface EvidenceItem {
  concept_id: string;
  evidence_type: string;
  confidence: string;
  repository: RepositoryIdentity;
  file_path: string | null;
  detail: string;
}

/** `status` is always one of these three neutral values -- never a
 * verdict like "failed"/"missing_skill" (see gitscore.matching.MatchStatus). */
export type RequirementStatus = "supported" | "not_observed" | "not_assessable";

export type Necessity = "required" | "preferred";

/** Milestone 9C -- WHY a requirement's `status` is what it is, without
 * introducing a new status value. "recognized" covers both `supported`
 * and `not_observed` (the requirement had a structured, GitHub-
 * observable concept mapping the matcher could evaluate). Within
 * `not_assessable`, "non_technical" is a genuine claim GitHub evidence
 * cannot speak to at all; "unparsed_placeholder" is GitScore's OWN
 * parser uncertainty -- never rendered identically to a genuine
 * non-technical claim. This is the field the UI should branch on;
 * `category` (below) is raw passthrough for transparency/debugging. */
export type InterpretationStatus = "recognized" | "non_technical" | "unparsed_placeholder";

/** Milestone 11-G19 (scoring v2) -- WHY a requirement does not count
 * toward `github_evidence_alignment`. A closed set mirroring
 * `gitscore.assessment.AlignmentExclusionReason`; never free text.
 * "alternative" = at least one acceptable option CAN be checked from
 * GitHub (a mixed "A or B" group); "technology" = none can. "unresolved"
 * = GitScore cannot tell whether GitHub evidence could exist;
 * "without_evidence_pathway" = it is known that no detector covers it. */
export type AlignmentExclusionReason =
  | "not_assessable"
  | "unresolved_technology"
  | "unresolved_alternative"
  | "technology_without_evidence_pathway"
  | "alternative_without_evidence_pathway";

export interface RequirementItem {
  text: string;
  status: RequirementStatus;
  necessity: Necessity;
  importance: string;
  github_observability: string;
  parser_confidence: string | null;
  concept_id: string | null;
  /** Milestone 9E, additive. Short human-readable label for `concept_id`
   * (e.g. "infra.kubernetes" -> "Kubernetes"). `null` exactly when
   * `concept_id` is `null`. Exists so a UI can disambiguate two distinct
   * requirement rows that share identical `text` (one job-posting
   * sentence can legitimately produce one row per matched concept --
   * e.g. "Docker and Kubernetes"), including when they land under
   * different, even contradictory, statuses. */
  concept_label: string | null;
  /** Milestone 9C, additive. Raw `JobRequirement.category` passthrough. */
  category: string | null;
  /** Milestone 9C, additive. See `InterpretationStatus`'s own doc comment. */
  interpretation_status: InterpretationStatus;
  alternative_concept_ids: string[];
  matched_concept_ids: string[];
  evidence: EvidenceItem[];
  /** Milestone 11-G19, additive. Whether this row is in the alignment
   * score's numerator/denominator. Independent of `status`: a `supported`
   * or `not_observed` row can be excluded and keeps its status and
   * evidence. Every `not_assessable` row is `false`. */
  counts_toward_alignment: boolean;
  /** Milestone 11-G19, additive. `null` exactly when counted. */
  alignment_exclusion_reason: AlignmentExclusionReason | null;
}

/** Milestone 9C, additive -- one claim segmentation judged requirement-
 * shaped for which NO RequirementItem was ever produced at all. No
 * status, concept, or necessity -- nothing downstream of segmentation
 * ever saw this claim. Always a SEPARATE list from `requirements.*`,
 * never merged into `not_assessable`. */
export interface UnparsedClaim {
  text: string;
}

export interface Subscore {
  supported: number;
  assessable: number;
}

export interface AnalysisMeta {
  github_username: string;
  job_title: string | null;
  job_company: string | null;
}

export interface Assessment {
  /** `null` when nothing was assessable -- NEVER 0/"N/A"/-1. */
  github_evidence_alignment: number | null;
  assessable_requirement_count: number;
  /** Milestone 9C, additive -- count of `not_assessable` requirements
   * whose `interpretation_status === "unparsed_placeholder"`. These DID
   * become a real requirement row (visible in `requirements.not_assessable`).
   * Informational only: never affects `github_evidence_alignment` or
   * `assessable_requirement_count`. */
  uninterpreted_requirement_count: number;
  /** Milestone 9E, additive -- count of `AnalyzeResponse.unparsed_claims`:
   * claims that never became a requirement row at all (a strictly more
   * severe gap than the placeholder above). Kept as a SEPARATE count,
   * deliberately never summed with `uninterpreted_requirement_count` --
   * see `unparsedClaimsCaveat()` in `lib/labels.ts`. These are NOT
   * confirmed job requirements and must never be labeled as such. */
  unparsed_claim_count: number;
  /** Milestone 11-G19, additive (scoring v2). `supported` + `not_observed`
   * rows that do NOT count toward the score. Reconciles exactly:
   * supported.length + not_observed.length ===
   * assessable_requirement_count + excluded_from_alignment_count. */
  excluded_from_alignment_count: number;
}

export interface RepositoryAnalysis {
  discovered: number;
  analyzed: number;
  partially_analyzed: number;
  complete: boolean;
}

export interface RequirementGroups {
  supported: RequirementItem[];
  not_observed: RequirementItem[];
  not_assessable: RequirementItem[];
}

export interface Diagnostics {
  extraction_failure_count: number;
  unknown_dependency_count: number;
}

export interface Versions {
  matcher: string;
  scoring: string;
  job_parser: string;
  evidence_schema: number;
}

export interface AnalyzeResponse {
  analysis: AnalysisMeta;
  assessment: Assessment;
  /** `null` when no REQUIRED requirement was assessable -- never `{supported: 0, assessable: 0}`. */
  required: Subscore | null;
  /** Same as `required`, for PREFERRED. */
  preferred: Subscore | null;
  repository_analysis: RepositoryAnalysis;
  requirements: RequirementGroups;
  /** Milestone 9C, additive -- usually empty. See `UnparsedClaim`'s own
   * doc comment. */
  unparsed_claims: UnparsedClaim[];
  diagnostics: Diagnostics;
  versions: Versions;
}

export interface HealthResponse {
  status: string;
}

export interface ErrorDetail {
  code: string;
  message: string;
  retryable: boolean;
}

export interface ErrorResponse {
  error: ErrorDetail;
}
