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

export interface RequirementItem {
  text: string;
  status: RequirementStatus;
  necessity: Necessity;
  importance: string;
  github_observability: string;
  parser_confidence: string | null;
  concept_id: string | null;
  alternative_concept_ids: string[];
  matched_concept_ids: string[];
  evidence: EvidenceItem[];
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
