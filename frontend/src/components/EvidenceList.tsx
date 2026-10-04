import type { EvidenceItem } from "@/types/api";
import { confidenceLabel, evidenceTypeLabel } from "@/lib/labels";

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
 * Renders ONLY facts the API actually supplied -- no fabricated GitHub
 * URL, file URL, source line, star count, or commit activity (none of
 * that exists on `EvidenceItem`).
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
            <span className="evidence-repository-name">
              {group.owner}/{group.name}
            </span>
            <ul>
              {group.items.map((item, index) => (
                <li key={`${group.key}-${index}`} className="evidence-detail">
                  <span className="evidence-type">{evidenceTypeLabel(item.evidence_type)}</span>
                  {item.file_path && <span className="evidence-file-path"> — {item.file_path}</span>}
                  <span className="evidence-confidence"> ({confidenceLabel(item.confidence)} confidence)</span>
                  <div className="evidence-detail-text">{item.detail}</div>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </div>
  );
}
