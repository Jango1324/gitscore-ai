import type { RequirementItem, RequirementStatus } from "@/types/api";
import { necessityLabel, requirementSectionCopy } from "@/lib/labels";
import { EvidenceList } from "@/components/EvidenceList";

interface RequirementSectionProps {
  status: RequirementStatus;
  requirements: RequirementItem[];
}

/**
 * One of the three requirement groups (supported / not_observed /
 * not_assessable). Section titles and explanations use the exact
 * neutral wording the product requires -- see `lib/labels.ts`'s
 * `requirementSectionCopy()`, the single place that wording lives.
 */
export function RequirementSection({ status, requirements }: RequirementSectionProps) {
  const { title, explanation } = requirementSectionCopy(status);
  const headingId = `requirement-section-${status}`;

  return (
    <section className="requirement-section" aria-labelledby={headingId}>
      <h2 id={headingId}>{title}</h2>
      {explanation && <p className="requirement-section-explanation">{explanation}</p>}
      {requirements.length === 0 ? (
        <p className="empty-note">None.</p>
      ) : (
        <ul className="requirement-list">
          {requirements.map((requirement, index) => (
            <li key={index} className="requirement-item">
              <p className="requirement-text">{requirement.text}</p>
              <span className="requirement-necessity">{necessityLabel(requirement.necessity)}</span>
              <EvidenceList evidence={requirement.evidence} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
