interface AlignmentHeadlineProps {
  alignment: number | null;
}

/**
 * The approved product name is "GitHub Evidence Alignment" -- never
 * "Job Fit"/"Qualification Score"/"Hiring Score"/"Hire Probability".
 * `null` renders as "Not available" with an explanation -- never
 * 0/NaN/undefined/-1 (Milestone 8A's own null-vs-zero distinction,
 * carried through to the UI).
 */
export function AlignmentHeadline({ alignment }: AlignmentHeadlineProps) {
  return (
    <section className="alignment-headline" aria-labelledby="alignment-heading">
      <h2 id="alignment-heading">GitHub Evidence Alignment</h2>
      {alignment === null ? (
        <>
          <p className="alignment-value alignment-value--unavailable">Not available</p>
          <p className="alignment-note">
            No job requirements could be meaningfully assessed from GitHub evidence.
          </p>
        </>
      ) : (
        <p className="alignment-value">
          <span className="alignment-number">{alignment}</span>
          <span className="alignment-scale"> / 100</span>
        </p>
      )}
    </section>
  );
}
