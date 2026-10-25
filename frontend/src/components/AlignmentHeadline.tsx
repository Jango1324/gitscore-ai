import { uninterpretedCaveat, unparsedClaimsCaveat } from "@/lib/labels";

interface AlignmentHeadlineProps {
  alignment: number | null;
  /** Milestone 9C, additive -- count of requirements GitScore's own
   * parser could not confidently interpret. Purely a caveat note; never
   * changes `alignment` itself. */
  uninterpretedCount?: number;
  /** Milestone 9E, additive -- count of statements that never became a
   * requirement row at all (`assessment.unparsed_claim_count`). A
   * SEPARATE caveat from `uninterpretedCount` -- see `unparsedClaimsCaveat()`
   * in `lib/labels.ts` for why the two are never summed into one number.
   * Purely informational; never changes `alignment`. */
  unparsedClaimCount?: number;
}

/**
 * The approved product name is "GitHub Evidence Alignment" -- never
 * "Job Fit"/"Qualification Score"/"Hiring Score"/"Hire Probability".
 * `null` renders as "Not available" with an explanation -- never
 * 0/NaN/undefined/-1 (Milestone 8A's own null-vs-zero distinction,
 * carried through to the UI).
 */
export function AlignmentHeadline({
  alignment,
  uninterpretedCount = 0,
  unparsedClaimCount = 0,
}: AlignmentHeadlineProps) {
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
      {uninterpretedCount > 0 && (
        <p className="alignment-uninterpreted-caveat">{uninterpretedCaveat(uninterpretedCount)}</p>
      )}
      {unparsedClaimCount > 0 && (
        <p className="alignment-unparsed-claims-caveat">{unparsedClaimsCaveat(unparsedClaimCount)}</p>
      )}
    </section>
  );
}
