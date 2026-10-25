import type { InterpretationStatus, RequirementItem, RequirementStatus } from "@/types/api";
import { necessityLabel, notAssessableSubsectionCopy, requirementSectionCopy } from "@/lib/labels";
import { EvidenceList } from "@/components/EvidenceList";

interface RequirementSectionProps {
  status: RequirementStatus;
  requirements: RequirementItem[];
  /** Milestone 9E Workstream B, additive, optional (defaults to empty --
   * existing callers/tests that don't pass it see identical rendering
   * to before this milestone). `text` values that appear more than once
   * across the WHOLE result (see `ResultView.findDuplicateRequirementTexts`),
   * not just within this one section/subsection. When a row's `text` is
   * in this set AND it has a `concept_label`, the label is appended so
   * two rows sharing identical text (one job-posting sentence, multiple
   * matched concepts -- e.g. "Docker and Kubernetes") never read as an
   * unexplained duplicate or, worse, a self-contradiction when they land
   * under different statuses. */
  duplicateTexts?: ReadonlySet<string>;
}

/** The exact text to render for one requirement row: `requirement.text`
 * unchanged, UNLESS it is one of several rows across the result sharing
 * identical text AND this row has a `concept_label` to disambiguate it
 * with -- never alters `requirement.text` itself, never applied when no
 * label exists (never fabricates a distinguishing label). */
function disambiguatedRequirementText(requirement: RequirementItem, duplicateTexts: ReadonlySet<string>): string {
  if (requirement.concept_label && duplicateTexts.has(requirement.text)) {
    return `${requirement.text} (${requirement.concept_label})`;
  }
  return requirement.text;
}

/** Shared rendering for one flat list of requirements -- used both by
 * the plain supported/not_observed sections and by each of
 * not_assessable's two subsections (Milestone 9C), so the actual `<li>`
 * markup/evidence rendering exists in exactly one place. */
function RequirementItemsList({
  requirements,
  duplicateTexts = new Set(),
}: {
  requirements: RequirementItem[];
  duplicateTexts?: ReadonlySet<string>;
}) {
  if (requirements.length === 0) {
    return <p className="empty-note">None.</p>;
  }
  return (
    <ul className="requirement-list">
      {requirements.map((requirement, index) => (
        <li key={index} className="requirement-item">
          <p className="requirement-text">{disambiguatedRequirementText(requirement, duplicateTexts)}</p>
          <span className="requirement-necessity">{necessityLabel(requirement.necessity)}</span>
          <EvidenceList evidence={requirement.evidence} />
        </li>
      ))}
    </ul>
  );
}

/** One not_assessable subsection (Milestone 9C) -- "non_technical" or
 * "unparsed_placeholder". A plain `<h3>` nested inside the outer
 * `not_assessable` `<section>`, never a second top-level `<h2>`, so the
 * page's heading hierarchy stays correct and the outer section's own
 * "None." empty-state (RequirementSection below, when BOTH subsections
 * are empty) and this subsection's empty-state never conflict. */
function NotAssessableSubsection({
  kind,
  requirements,
  duplicateTexts,
}: {
  kind: Exclude<InterpretationStatus, "recognized">;
  requirements: RequirementItem[];
  duplicateTexts: ReadonlySet<string>;
}) {
  const { title, explanation } = notAssessableSubsectionCopy(kind);
  const headingId = `requirement-subsection-${kind}`;
  return (
    <div className="requirement-subsection" aria-labelledby={headingId}>
      <h3 id={headingId}>{title}</h3>
      <p className="requirement-section-explanation">{explanation}</p>
      <RequirementItemsList requirements={requirements} duplicateTexts={duplicateTexts} />
    </div>
  );
}

/**
 * One of the three requirement groups (supported / not_observed /
 * not_assessable). Section titles and explanations use the exact
 * neutral wording the product requires -- see `lib/labels.ts`'s
 * `requirementSectionCopy()`, the single place that wording lives.
 *
 * Milestone 9C: `not_assessable` is further split into two subsections
 * by `interpretation_status` -- a genuinely non-technical claim (e.g.
 * "Bachelor's degree") must never read identically to GitScore's own
 * parser uncertainty (e.g. a Milestone 9A `unresolved_requirement`
 * placeholder). `supported`/`not_observed` are rendered exactly as
 * before this milestone.
 */
export function RequirementSection({ status, requirements, duplicateTexts = new Set() }: RequirementSectionProps) {
  const { title, explanation } = requirementSectionCopy(status);
  const headingId = `requirement-section-${status}`;

  if (status === "not_assessable") {
    const nonTechnical = requirements.filter((r) => r.interpretation_status === "non_technical");
    const unparsedPlaceholder = requirements.filter((r) => r.interpretation_status === "unparsed_placeholder");
    return (
      <section className="requirement-section" aria-labelledby={headingId}>
        <h2 id={headingId}>{title}</h2>
        {requirements.length === 0 ? (
          <p className="empty-note">None.</p>
        ) : (
          <>
            <NotAssessableSubsection kind="non_technical" requirements={nonTechnical} duplicateTexts={duplicateTexts} />
            <NotAssessableSubsection
              kind="unparsed_placeholder"
              requirements={unparsedPlaceholder}
              duplicateTexts={duplicateTexts}
            />
          </>
        )}
      </section>
    );
  }

  return (
    <section className="requirement-section" aria-labelledby={headingId}>
      <h2 id={headingId}>{title}</h2>
      {explanation && <p className="requirement-section-explanation">{explanation}</p>}
      <RequirementItemsList requirements={requirements} duplicateTexts={duplicateTexts} />
    </section>
  );
}
