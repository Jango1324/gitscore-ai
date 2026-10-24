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
 */
export function ResultView({ result }: ResultViewProps) {
  return (
    <div className="result-view">
      <AlignmentHeadline
        alignment={result.assessment.github_evidence_alignment}
        uninterpretedCount={result.assessment.uninterpreted_requirement_count}
      />
      <SubscoreRow required={result.required} preferred={result.preferred} />
      <RepositoryCoverage coverage={result.repository_analysis} />
      <RequirementSection status="supported" requirements={result.requirements.supported} />
      <RequirementSection status="not_observed" requirements={result.requirements.not_observed} />
      <RequirementSection status="not_assessable" requirements={result.requirements.not_assessable} />
      <UnparsedClaimsSection claims={result.unparsed_claims} />
      <DiagnosticsPanel
        diagnostics={result.diagnostics}
        versions={result.versions}
        partiallyAnalyzed={result.repository_analysis.partially_analyzed}
      />
    </div>
  );
}
