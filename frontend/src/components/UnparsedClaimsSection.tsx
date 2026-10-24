import type { UnparsedClaim } from "@/types/api";
import { UNPARSED_CLAIMS_SECTION_COPY } from "@/lib/labels";

interface UnparsedClaimsSectionProps {
  claims: UnparsedClaim[];
}

/**
 * Milestone 9C -- the fourth, clearly separate list: claims the parser's
 * segmentation step judged requirement-shaped but for which NO
 * requirement was produced at all. Deliberately rendered with no
 * status, necessity, or evidence (there is none to show) -- just the
 * original text, so the posting's own content is never silently hidden.
 * Omitted entirely when empty (unlike the three requirement groups,
 * which always render with a "None." empty-state) -- an empty
 * unparsed-claims list is the NORMAL, expected case for most postings,
 * and rendering an always-visible fourth section would make a routine
 * "nothing to report" look like a notable finding.
 */
export function UnparsedClaimsSection({ claims }: UnparsedClaimsSectionProps) {
  if (claims.length === 0) {
    return null;
  }
  return (
    <section className="unparsed-claims-section" aria-labelledby="unparsed-claims-heading">
      <h2 id="unparsed-claims-heading">{UNPARSED_CLAIMS_SECTION_COPY.title}</h2>
      <p className="requirement-section-explanation">{UNPARSED_CLAIMS_SECTION_COPY.explanation}</p>
      <ul className="unparsed-claims-list">
        {claims.map((claim, index) => (
          <li key={index} className="unparsed-claim-item">
            {claim.text}
          </li>
        ))}
      </ul>
    </section>
  );
}
