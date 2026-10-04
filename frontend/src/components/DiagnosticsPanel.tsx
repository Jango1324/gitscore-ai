import type { Diagnostics, Versions } from "@/types/api";

interface DiagnosticsPanelProps {
  diagnostics: Diagnostics;
  versions: Versions;
  partiallyAnalyzed: number;
}

/**
 * Secondary, de-emphasized, collapsed by default -- never placed above
 * candidate evidence (Milestone 8B Part 20). A non-zero extraction
 * failure count surfaces a modest, neutral warning OUTSIDE the
 * collapsed <details> (so it's visible without expanding), but never
 * implies the whole analysis failed -- partial per-repository
 * extraction issues are expected, isolated failures (Milestone 5D),
 * not a product-level error.
 */
export function DiagnosticsPanel({ diagnostics, versions, partiallyAnalyzed }: DiagnosticsPanelProps) {
  return (
    <section className="diagnostics-panel">
      {diagnostics.extraction_failure_count > 0 && (
        <p className="diagnostics-warning">
          Some repository evidence could not be analyzed ({diagnostics.extraction_failure_count}{" "}
          {diagnostics.extraction_failure_count === 1 ? "source" : "sources"} affected across{" "}
          {partiallyAnalyzed} {partiallyAnalyzed === 1 ? "repository" : "repositories"}).
        </p>
      )}
      <details>
        <summary>Analysis details</summary>
        <dl>
          <dt>Extraction failures</dt>
          <dd>{diagnostics.extraction_failure_count}</dd>
          <dt>Unrecognized dependencies seen</dt>
          <dd>{diagnostics.unknown_dependency_count}</dd>
          <dt>Matcher version</dt>
          <dd>{versions.matcher}</dd>
          <dt>Scoring version</dt>
          <dd>{versions.scoring}</dd>
          <dt>Job parser version</dt>
          <dd>{versions.job_parser}</dd>
          <dt>Evidence schema version</dt>
          <dd>{versions.evidence_schema}</dd>
        </dl>
      </details>
    </section>
  );
}
