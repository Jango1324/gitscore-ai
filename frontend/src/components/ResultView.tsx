import type { AnalyzeResponse } from "@/types/api";
import { AlignmentHeadline } from "@/components/AlignmentHeadline";
import { SubscoreRow } from "@/components/SubscoreRow";
import { RepositoryCoverage } from "@/components/RepositoryCoverage";
import { RequirementSection } from "@/components/RequirementSection";
import { DiagnosticsPanel } from "@/components/DiagnosticsPanel";

interface ResultViewProps {
  result: AnalyzeResponse;
}

/**
 * Composes every result section in the required information
 * hierarchy (Milestone 8B Part 5): alignment, required/preferred,
 * repository coverage, supported, not observed, not assessable,
 * diagnostics last.
 */
export function ResultView({ result }: ResultViewProps) {
  return (
    <div className="result-view">
      <AlignmentHeadline alignment={result.assessment.github_evidence_alignment} />
      <SubscoreRow required={result.required} preferred={result.preferred} />
      <RepositoryCoverage coverage={result.repository_analysis} />
      <RequirementSection status="supported" requirements={result.requirements.supported} />
      <RequirementSection status="not_observed" requirements={result.requirements.not_observed} />
      <RequirementSection status="not_assessable" requirements={result.requirements.not_assessable} />
      <DiagnosticsPanel
        diagnostics={result.diagnostics}
        versions={result.versions}
        partiallyAnalyzed={result.repository_analysis.partially_analyzed}
      />
    </div>
  );
}
