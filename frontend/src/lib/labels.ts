/**
 * Milestone 8B -- display-only label lookups.
 *
 * Purely cosmetic: turns an API enum VALUE into a human-readable string
 * for rendering. Never changes which value is present, never invents a
 * new status/category -- an unrecognized value still renders (falls
 * back to the raw value) rather than disappearing.
 */
import type { InterpretationStatus, RequirementStatus } from "@/types/api";

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

/**
 * Milestone 9E Workstream C -- a short, calibrated, one-sentence
 * description of what a given `evidence_type` actually represents,
 * shown alongside its label. Never a numeric strength/confidence score
 * (none is invented here) -- just a plain-language statement of the
 * KIND of observation this is, so a reader can judge for themselves
 * whether (for example) a README mention is as strong a signal as a
 * dependency-manifest declaration, rather than treating every
 * "supported" requirement as equally well-evidenced.
 */
const EVIDENCE_TYPE_DESCRIPTIONS: Record<string, string> = {
  repository_language: "The repository's own reported language composition (GitHub language statistics).",
  repository_metadata: "Repository-level metadata (such as its description or topics), not its code content.",
  readme: "A text mention found in the repository's README -- may describe the candidate's own usage, or only a reference, comparison, or example.",
  dependency: "An explicit dependency declared in a project manifest (e.g. requirements.txt, package.json).",
  source_import: "An import statement found directly in source code.",
  config: "A configuration file present in the repository.",
  docker: "Docker/containerization files present in the repository.",
  ci: "CI configuration present in the repository.",
  test: "Test files present in the repository.",
  notebook: "A Jupyter notebook present in the repository.",
  deployment: "Deployment configuration present in the repository.",
};

export function evidenceTypeDescription(evidenceType: string): string | null {
  return EVIDENCE_TYPE_DESCRIPTIONS[evidenceType] ?? null;
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
    // Milestone 9C: no longer carries its own generic explanation --
    // the two subsections below (notAssessableSubsectionCopy) each
    // carry a MORE SPECIFIC explanation of why, which is strictly more
    // informative than one shared sentence covering both causes.
    explanation: "",
  },
};

export function requirementSectionCopy(status: RequirementStatus): { title: string; explanation: string } {
  return REQUIREMENT_SECTION_LABELS[status];
}

/**
 * Milestone 9C -- the two NOT_ASSESSABLE subsections. Deliberately
 * separate copy from `REQUIREMENT_SECTION_LABELS.not_assessable` above
 * (which remains the OUTER section heading/intro): a genuinely
 * non-technical claim (education, soft skills, ...) and GitScore's own
 * parser uncertainty must never read as the same kind of limitation --
 * one is a fact about the job posting, the other is a fact about
 * GitScore's own interpretation of it.
 */
const NOT_ASSESSABLE_SUBSECTION_LABELS: Record<
  Exclude<InterpretationStatus, "recognized">,
  { title: string; explanation: string }
> = {
  non_technical: {
    title: "Genuinely non-technical requirements",
    explanation: "GitHub evidence cannot reliably establish these requirements.",
  },
  unparsed_placeholder: {
    title: "Could not be confidently interpreted",
    explanation:
      "GitScore's own parser could not confidently interpret this requirement as a specific technology or skill. This is a limitation of GitScore's reading of the job text, not a statement about the candidate or about whether the requirement matters.",
  },
};

export function notAssessableSubsectionCopy(
  kind: Exclude<InterpretationStatus, "recognized">,
): { title: string; explanation: string } {
  return NOT_ASSESSABLE_SUBSECTION_LABELS[kind];
}

/** Milestone 9C -- the small, non-alarming caveat shown near the
 * alignment headline when GitScore's own parser uncertainty may be
 * affecting what could be assessed. Singular/plural handled once here,
 * not duplicated at each call site. Covers ONLY claims that became a
 * real requirement row (`interpretation_status === "unparsed_placeholder"`)
 * -- see `unparsedClaimsCaveat()` below for the separate, strictly more
 * severe category this deliberately does NOT include (Milestone 9E
 * Workstream A; `docs/evaluation/MILESTONE_9D_PRODUCT_VALIDATION.md`
 * §6.1 found the prior single-count headline undercounted real
 * interpretive uncertainty by excluding that category entirely). */
export function uninterpretedCaveat(count: number): string {
  const plural = count === 1 ? "requirement" : "requirements";
  return `${count} ${plural} could not be confidently interpreted by GitScore's parser -- see below.`;
}

/** Milestone 9E Workstream A -- the second, SEPARATE headline caveat for
 * `assessment.unparsed_claim_count`: statements the job posting appears
 * to contain that never became a requirement row at all (no status, no
 * concept -- see `UnparsedClaimsSection`). Deliberately says
 * "statements," never "requirements" -- these are not confirmed job
 * requirements, just text GitScore could not interpret well enough to
 * assess at all. Kept as its own sentence rather than summed with
 * `uninterpretedCaveat()`'s count: the two categories are not the same
 * fact (one produced an inspectable row, this one did not), and forcing
 * them into one number would misrepresent the more severe category as
 * the less severe one. */
export function unparsedClaimsCaveat(count: number): string {
  const plural = count === 1 ? "statement" : "statements";
  return `${count} additional ${plural} in the job posting could not be parsed as a requirement at all -- see below.`;
}

/** Milestone 9C -- heading/explanation for the fourth, clearly separate
 * list of claims that produced no requirement at all (an `UnparsedClaim`
 * -- see that type's own doc comment). */
export const UNPARSED_CLAIMS_SECTION_COPY = {
  title: "Statements GitScore could not parse as requirements",
  explanation:
    "GitScore identified these statements in the job posting as possible requirements, but could not interpret them well enough to assess at all. They are shown here exactly as written, with no status or evidence, so nothing about the posting is silently hidden.",
};
