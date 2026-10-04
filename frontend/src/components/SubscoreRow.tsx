import type { Subscore } from "@/types/api";

interface SubscoreCardProps {
  label: string;
  subscore: Subscore | null;
}

function SubscoreCard({ label, subscore }: SubscoreCardProps) {
  return (
    <div className="subscore-card">
      <h3>{label}</h3>
      {subscore === null ? (
        <p>No {label.toLowerCase()} requirements were assessable</p>
      ) : (
        <p>
          {subscore.supported} of {subscore.assessable} supported
        </p>
      )}
    </div>
  );
}

interface SubscoreRowProps {
  required: Subscore | null;
  preferred: Subscore | null;
}

/**
 * Required/preferred render immediately beneath the headline, never
 * hidden inside a collapsed section -- the adversarial "strong headline
 * despite zero required support" case (Milestone 7B) needs these facts
 * visually prominent, not an afterthought.
 */
export function SubscoreRow({ required, preferred }: SubscoreRowProps) {
  return (
    <section className="subscore-row" aria-label="Required and preferred requirement support">
      <SubscoreCard label="Required" subscore={required} />
      <SubscoreCard label="Preferred" subscore={preferred} />
    </section>
  );
}
