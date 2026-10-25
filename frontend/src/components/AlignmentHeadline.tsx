import type { UnparsedClaim } from "@/types/api";
import {
  coverageGapExample,
  coverageGapSummary,
  hasKnownCoverageGap,
  KNOWN_COVERAGE_GAP_LABEL,
  uninterpretedCaveat,
  unparsedClaimsCaveat,
} from "@/lib/labels";

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
  /** Milestone 9G, additive -- the actual `unparsed_claims` array
   * (verbatim text, nothing else), used ONLY to name a concrete excerpt
   * of what the score excludes (`coverageGapExample()`). The boolean
   * "is there a known gap at all" decision is made entirely from the
   * two counts above (`hasKnownCoverageGap()`) -- this array never
   * contributes to THAT decision, only to what text is quoted once a
   * gap is already known to exist. */
  unparsedClaims?: UnparsedClaim[];
}

/**
 * The approved product name is "GitHub Evidence Alignment" -- never
 * "Job Fit"/"Qualification Score"/"Hiring Score"/"Hire Probability".
 * `null` renders as "Not available" with an explanation -- never
 * 0/NaN/undefined/-1 (Milestone 8A's own null-vs-zero distinction,
 * carried through to the UI).
 *
 * Milestone 9G adds a visible "Known coverage gaps" badge beside the
 * score (number OR "Not available") whenever `hasKnownCoverageGap()` is
 * true, plus a general sentence and, where real claim text is
 * available, a concrete, verbatim excerpt naming it -- all purely
 * presentational, computed entirely from fields the API already
 * returns (`uninterpretedCount`/`unparsedClaimCount`/`unparsedClaims`).
 * Deliberately NEVER renders any "Complete"/"Fully analyzed"/"100%
 * requirements interpreted" affirmation when no gap is known -- absence
 * of a known diagnostic is not proof of exhaustive parsing (M9F §5.4).
 */
export function AlignmentHeadline({
  alignment,
  uninterpretedCount = 0,
  unparsedClaimCount = 0,
  unparsedClaims = [],
}: AlignmentHeadlineProps) {
  const hasGap = hasKnownCoverageGap(uninterpretedCount, unparsedClaimCount);
  const gapExample = coverageGapExample(unparsedClaims);
  return (
    <section className="alignment-headline" aria-labelledby="alignment-heading">
      <h2 id="alignment-heading">GitHub Evidence Alignment</h2>
      {alignment === null ? (
        <>
          <p className="alignment-value alignment-value--unavailable">
            <span>Not available</span>
            {hasGap && <span className="coverage-gap-badge">{KNOWN_COVERAGE_GAP_LABEL}</span>}
          </p>
          <p className="alignment-note">
            No job requirements could be meaningfully assessed from GitHub evidence.
          </p>
        </>
      ) : (
        <p className="alignment-value">
          <span className="alignment-number">{alignment}</span>
          <span className="alignment-scale"> / 100</span>
          {hasGap && <span className="coverage-gap-badge">{KNOWN_COVERAGE_GAP_LABEL}</span>}
        </p>
      )}
      {hasGap && <p className="alignment-coverage-gap-summary">{coverageGapSummary()}</p>}
      {hasGap && gapExample && <p className="alignment-coverage-gap-example">{gapExample}</p>}
      {uninterpretedCount > 0 && (
        <p className="alignment-uninterpreted-caveat">{uninterpretedCaveat(uninterpretedCount)}</p>
      )}
      {unparsedClaimCount > 0 && (
        <p className="alignment-unparsed-claims-caveat">{unparsedClaimsCaveat(unparsedClaimCount)}</p>
      )}
    </section>
  );
}
