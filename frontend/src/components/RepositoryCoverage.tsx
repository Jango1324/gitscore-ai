import type { RepositoryAnalysis } from "@/types/api";

interface RepositoryCoverageProps {
  coverage: RepositoryAnalysis;
}

/**
 * Factual discovered/analyzed counts only -- the backend deliberately
 * defines no "coverage percentage" semantic (Milestone 8A), so this
 * component never computes or displays one.
 */
export function RepositoryCoverage({ coverage }: RepositoryCoverageProps) {
  const { discovered, analyzed, complete } = coverage;

  return (
    <section className="repository-coverage" aria-labelledby="repository-coverage-heading">
      <h2 id="repository-coverage-heading">Repository analysis</h2>
      {discovered === 0 ? (
        <p>No repositories were discovered on this account.</p>
      ) : complete ? (
        <p>All {discovered} discovered repositories were deeply analyzed.</p>
      ) : (
        <>
          <p>
            {analyzed} of {discovered} repositories deeply analyzed
          </p>
          <p className="repository-coverage-note">
            Highest-ranked repositories were prioritized; not every discovered repository was deeply
            analyzed.
          </p>
        </>
      )}
    </section>
  );
}
