import type { AnalyzeResponse } from "@/types/api";
import { AlignmentHeadline } from "@/components/AlignmentHeadline";
import { SubscoreRow } from "@/components/SubscoreRow";
import { RepositoryCoverage } from "@/components/RepositoryCoverage";
import { RequirementSection } from "@/components/RequirementSection";
import { UnparsedClaimsSection } from "@/components/UnparsedClaimsSection";
import { DiagnosticsPanel } from "@/components/DiagnosticsPanel";

interface ResultViewProps {
  result: AnalyzeResponse;
}

/**
 * Milestone 9E Workstream B -- which requirement `text` values appear
 * more than once across the WHOLE result (not just within one status
 * group). One job-posting sentence can legitimately produce multiple
 * `JobRequirement` rows sharing identical `original_text` -- one per
 * matched concept (Milestone 9A/6B.1's own "one row per concept"
 * design, e.g. "Docker and Kubernetes") -- including rows that land
 * under DIFFERENT, even contradictory, statuses (one `supported`, one
 * `not_observed`). Computed globally here, not per-section, because
 * that cross-status case (`docs/evaluation/MILESTONE_9D_PRODUCT_VALIDATION.md`
 * §6.5) is the most confusing instance and a per-section count alone
 * would miss it.
 */
function findDuplicateRequirementTexts(result: AnalyzeResponse): ReadonlySet<string> {
  const counts = new Map<string, number>();
  const all = [
    ...result.requirements.supported,
    ...result.requirements.not_observed,
    ...result.requirements.not_assessable,
  ];
  for (const requirement of all) {
    counts.set(requirement.text, (counts.get(requirement.text) ?? 0) + 1);
  }
  const duplicates = new Set<string>();
  for (const [text, count] of counts) {
    if (count > 1) {
      duplicates.add(text);
    }
  }
  return duplicates;
}

/**
 * Composes every result section in the required information
 * hierarchy (Milestone 8B Part 5): alignment, required/preferred,
 * repository coverage, supported, not observed, not assessable,
 * diagnostics last.
 *
 * Milestone 9C adds the `uninterpretedCount` caveat on the headline
 * (purely informational -- `alignment` itself is unchanged) and a
 * fourth, clearly separate `UnparsedClaimsSection` after the three
 * requirement groups and before diagnostics -- it is a parsing
 * diagnostic, not a requirement verdict, so it sits alongside
 * `DiagnosticsPanel` in the hierarchy rather than among
 * supported/not_observed/not_assessable.
 *
 * Milestone 9E adds a SECOND, separate headline caveat
 * (`unparsedClaimCount`, Workstream A) and computes
 * `findDuplicateRequirementTexts()` once here to disambiguate
 * duplicate-looking requirement rows (Workstream B) -- passed down to
 * every `RequirementSection` rather than re-derived per section.
 */
export function ResultView({ result }: ResultViewProps) {
  const duplicateTexts = findDuplicateRequirementTexts(result);
  return (
    <div className="result-view">
      <AlignmentHeadline
        alignment={result.assessment.github_evidence_alignment}
        uninterpretedCount={result.assessment.uninterpreted_requirement_count}
        unparsedClaimCount={result.assessment.unparsed_claim_count}
      />
      <SubscoreRow required={result.required} preferred={result.preferred} />
      <RepositoryCoverage coverage={result.repository_analysis} />
      <RequirementSection status="supported" requirements={result.requirements.supported} duplicateTexts={duplicateTexts} />
      <RequirementSection status="not_observed" requirements={result.requirements.not_observed} duplicateTexts={duplicateTexts} />
      <RequirementSection status="not_assessable" requirements={result.requirements.not_assessable} duplicateTexts={duplicateTexts} />
      <UnparsedClaimsSection claims={result.unparsed_claims} />
      <DiagnosticsPanel
        diagnostics={result.diagnostics}
        versions={result.versions}
        partiallyAnalyzed={result.repository_analysis.partially_analyzed}
      />
    </div>
  );
}
