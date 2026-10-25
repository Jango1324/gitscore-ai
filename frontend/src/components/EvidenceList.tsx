import type { EvidenceItem } from "@/types/api";
import { confidenceLabel, evidenceTypeDescription, evidenceTypeLabel } from "@/lib/labels";
import { repositoryUrl } from "@/lib/github";

interface EvidenceListProps {
  evidence: EvidenceItem[];
}

interface RepositoryGroup {
  key: string;
  owner: string;
  name: string;
  items: EvidenceItem[];
}

function groupByRepository(evidence: EvidenceItem[]): RepositoryGroup[] {
  const groups = new Map<string, RepositoryGroup>();
  for (const item of evidence) {
    const key = `${item.repository.owner}/${item.repository.name}`;
    const existing = groups.get(key);
    if (existing) {
      existing.items.push(item);
    } else {
      groups.set(key, {
        key,
        owner: item.repository.owner,
        name: item.repository.name,
        items: [item],
      });
    }
  }
  return Array.from(groups.values());
}

/**
 * Renders ONLY facts the API actually supplied -- no fabricated file
 * URL, source line, star count, or commit activity (none of that exists
 * on `EvidenceItem`).
 *
 * Milestone 9E Workstream C: the repository name links to
 * `https://github.com/{owner}/{name}` (`lib/github.ts`) -- constructed
 * from the SAME `owner`/`name` already shown as plain text before this
 * milestone, never a new or guessed fact (no file-specific deep link:
 * see `repositoryUrl()`'s own docstring for why). Each evidence item
 * also shows a short, calibrated, one-sentence description of what its
 * `evidence_type` actually represents (`evidenceTypeDescription()`) --
 * never a new numeric strength score -- so a reader can judge for
 * themselves whether (for example) a README mention is as strong a
 * signal as a dependency-manifest declaration.
 */
export function EvidenceList({ evidence }: EvidenceListProps) {
  if (evidence.length === 0) {
    return null;
  }

  const groups = groupByRepository(evidence);

  return (
    <div className="evidence-list">
      <p className="evidence-list-heading">Supported by:</p>
      <ul>
        {groups.map((group) => (
          <li key={group.key} className="evidence-repository">
            <a
              className="evidence-repository-name"
              href={repositoryUrl(group.owner, group.name)}
              target="_blank"
              rel="noopener noreferrer"
            >
              {group.owner}/{group.name}
            </a>
            <ul>
              {group.items.map((item, index) => {
                const description = evidenceTypeDescription(item.evidence_type);
                return (
                  <li key={`${group.key}-${index}`} className="evidence-detail">
                    <span className="evidence-type">{evidenceTypeLabel(item.evidence_type)}</span>
                    {item.file_path && <span className="evidence-file-path"> — {item.file_path}</span>}
                    <span className="evidence-confidence"> ({confidenceLabel(item.confidence)} confidence)</span>
                    {description && <p className="evidence-type-description">{description}</p>}
                    <div className="evidence-detail-text">{item.detail}</div>
                  </li>
                );
              })}
            </ul>
          </li>
        ))}
      </ul>
    </div>
  );
}
