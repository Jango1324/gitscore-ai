import type { AnalyzeResponse, RequirementItem } from "@/types/api";

export function makeRequirement(overrides: Partial<RequirementItem> = {}): RequirementItem {
  return {
    text: "Experience with Docker",
    status: "not_observed",
    necessity: "required",
    importance: "medium",
    github_observability: "strongly_observable",
    parser_confidence: "high",
    concept_id: "infra.docker",
    alternative_concept_ids: [],
    matched_concept_ids: [],
    evidence: [],
    ...overrides,
  };
}

/** A full, realistic happy-path response (Backend Software Engineer, 2 supported). */
export function makeAnalyzeResponse(overrides: Partial<AnalyzeResponse> = {}): AnalyzeResponse {
  return {
    analysis: { github_username: "octocat", job_title: "Backend Software Engineer", job_company: null },
    assessment: { github_evidence_alignment: 40, assessable_requirement_count: 5 },
    required: { supported: 2, assessable: 3 },
    preferred: { supported: 0, assessable: 2 },
    repository_analysis: { discovered: 20, analyzed: 15, partially_analyzed: 0, complete: false },
    requirements: {
      supported: [
        makeRequirement({
          text: "3+ years of experience building Python backend services",
          status: "supported",
          concept_id: "language.python",
          matched_concept_ids: ["language.python"],
          evidence: [
            {
              concept_id: "language.python",
              evidence_type: "repository_language",
              confidence: "moderate",
              repository: { owner: "octocat", name: "api-service" },
              file_path: null,
              detail: "Python: 90.00% (9000 bytes)",
            },
          ],
        }),
        makeRequirement({
          text: "Familiarity with Docker",
          status: "supported",
          concept_id: "infra.docker",
          matched_concept_ids: ["infra.docker"],
          evidence: [
            {
              concept_id: "infra.docker",
              evidence_type: "docker",
              confidence: "strong",
              repository: { owner: "octocat", name: "api-service" },
              file_path: "Dockerfile",
              detail: "root file present: Dockerfile",
            },
          ],
        }),
      ],
      not_observed: [
        makeRequirement({ text: "Experience with PostgreSQL", concept_id: "database.postgresql" }),
        makeRequirement({
          text: "Experience with AWS",
          necessity: "preferred",
          importance: "low",
          concept_id: "cloud.aws",
        }),
        makeRequirement({
          text: "Experience with Next.js",
          necessity: "preferred",
          importance: "low",
          concept_id: "framework.nextjs",
        }),
      ],
      not_assessable: [
        makeRequirement({
          text: "3+ years of experience building Python backend services",
          status: "not_assessable",
          importance: "medium",
          github_observability: "not_observable",
          concept_id: null,
        }),
        makeRequirement({
          text: "Excellent written and verbal communication",
          status: "not_assessable",
          importance: "medium",
          github_observability: "not_observable",
          parser_confidence: "medium",
          concept_id: null,
        }),
      ],
    },
    diagnostics: { extraction_failure_count: 0, unknown_dependency_count: 0 },
    versions: {
      matcher: "requirement_matcher:v1",
      scoring: "github_evidence_alignment:v1",
      job_parser: "job_description_parser:v2",
      evidence_schema: 2,
    },
    ...overrides,
  };
}
