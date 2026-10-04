/**
 * Milestone 8B -- display-only label lookups.
 *
 * Purely cosmetic: turns an API enum VALUE into a human-readable string
 * for rendering. Never changes which value is present, never invents a
 * new status/category -- an unrecognized value still renders (falls
 * back to the raw value) rather than disappearing.
 */
import type { RequirementStatus } from "@/types/api";

const EVIDENCE_TYPE_LABELS: Record<string, string> = {
  repository_language: "Language usage",
  repository_metadata: "Repository metadata",
  readme: "README mention",
  dependency: "Dependency manifest",
  source_import: "Source import",
  config: "Configuration file",
  docker: "Docker / containerization",
  ci: "CI configuration",
  test: "Test suite",
  notebook: "Notebook",
  deployment: "Deployment configuration",
};

export function evidenceTypeLabel(evidenceType: string): string {
  return EVIDENCE_TYPE_LABELS[evidenceType] ?? evidenceType;
}

export function confidenceLabel(confidence: string): string {
  return confidence.length > 0 ? confidence[0]!.toUpperCase() + confidence.slice(1) : confidence;
}

export function necessityLabel(necessity: string): string {
  return necessity === "required" ? "Required" : necessity === "preferred" ? "Preferred" : necessity;
}

const REQUIREMENT_SECTION_LABELS: Record<RequirementStatus, { title: string; explanation: string }> = {
  supported: {
    title: "Supported by GitHub evidence",
    explanation: "",
  },
  not_observed: {
    title: "Not observed in analyzed GitHub evidence",
    explanation:
      "No supporting evidence was observed in the analyzed GitHub material. This does not mean the candidate lacks the skill.",
  },
  not_assessable: {
    title: "Not assessable from GitHub",
    explanation: "GitHub evidence cannot reliably establish these requirements.",
  },
};

export function requirementSectionCopy(status: RequirementStatus): { title: string; explanation: string } {
  return REQUIREMENT_SECTION_LABELS[status];
}
