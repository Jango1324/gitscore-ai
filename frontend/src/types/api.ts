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

export interface RequirementItem {
  text: string;
  status: RequirementStatus;
  necessity: Necessity;
  importance: string;
  github_observability: string;
  parser_confidence: string | null;
  concept_id: string | null;
  /** Milestone 9C, additive. Raw `JobRequirement.category` passthrough. */
  category: string | null;
  /** Milestone 9C, additive. See `InterpretationStatus`'s own doc comment. */
  interpretation_status: InterpretationStatus;
  alternative_concept_ids: string[];
  matched_concept_ids: string[];
  evidence: EvidenceItem[];
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
   * whose `interpretation_status === "unparsed_placeholder"`.
   * Informational only: never affects `github_evidence_alignment` or
   * `assessable_requirement_count`. */
  uninterpreted_requirement_count: number;
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
