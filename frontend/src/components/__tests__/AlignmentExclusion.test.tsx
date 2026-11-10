import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";

import { ResultView } from "@/components/ResultView";
import { makeAnalyzeResponse, makeRequirement } from "@/test/fixtures";

// Milestone 11-G19 (scoring v2) -- evaluated requirements that do not count
// toward the alignment score must be visibly disclosed, keep their status
// and evidence, and never read as a penalty or a missing skill.

const AWS_EVIDENCE = {
  concept_id: "cloud.aws",
  evidence_type: "readme_mention",
  confidence: "weak",
  repository: { owner: "octocat", name: "infra" },
  file_path: "README.md",
  detail: "Deployed on AWS Lambda",
};

function excludedResult(overrides: { alignment: number | null; assessable: number }) {
  return makeAnalyzeResponse({
    assessment: {
      github_evidence_alignment: overrides.alignment,
      assessable_requirement_count: overrides.assessable,
      uninterpreted_requirement_count: 0,
      unparsed_claim_count: 0,
      excluded_from_alignment_count: 2,
    },
    requirements: {
      supported: [
        makeRequirement({
          text: "Experience with AWS or Azure",
          status: "supported",
          concept_id: null,
          concept_label: null,
          alternative_concept_ids: ["cloud.aws", "unresolved:azure"],
          matched_concept_ids: ["cloud.aws"],
          evidence: [AWS_EVIDENCE],
          counts_toward_alignment: false,
          alignment_exclusion_reason: "unresolved_alternative",
        }),
      ],
      not_observed: [
        makeRequirement({ text: "Experience with PostgreSQL", concept_id: "database.postgresql" }),
        makeRequirement({
          text: "Python, Terraform, Docker",
          concept_id: "unresolved:terraform",
          concept_label: "terraform",
          counts_toward_alignment: false,
          alignment_exclusion_reason: "unresolved_technology",
        }),
      ],
      not_assessable: [
        makeRequirement({
          text: "Bachelor's degree in Computer Science",
          status: "not_assessable",
          concept_id: null,
          concept_label: null,
          category: "education",
          interpretation_status: "non_technical",
          counts_toward_alignment: false,
          alignment_exclusion_reason: "not_assessable",
        }),
      ],
    },
  });
}

describe("Alignment exclusion disclosure (scoring v2)", () => {
  it("shows a supported-but-excluded row as supported, with its evidence, labelled not counted", () => {
    render(<ResultView result={excludedResult({ alignment: 0, assessable: 1 })} />);
    const supported = screen.getByRole("region", { name: "Supported by GitHub evidence" });
    const item = within(supported).getByText("Experience with AWS or Azure").closest("li")!;
    expect(within(item).getByText("Not counted in alignment score")).toBeInTheDocument();
    expect(within(item).getByText(/At least one acceptable option in this requirement cannot be checked/)).toBeInTheDocument();
    expect(within(item).getByText("Deployed on AWS Lambda")).toBeInTheDocument();
  });

  it("distinguishes an excluded NOT_OBSERVED row from a counted one", () => {
    render(<ResultView result={excludedResult({ alignment: 0, assessable: 1 })} />);
    const notObserved = screen.getByRole("region", { name: "Not observed in analyzed GitHub evidence" });
    const counted = within(notObserved).getByText("Experience with PostgreSQL").closest("li")!;
    const excluded = within(notObserved).getByText("Python, Terraform, Docker").closest("li")!;
    expect(within(counted).queryByText("Not counted in alignment score")).not.toBeInTheDocument();
    expect(within(excluded).getByText("Not counted in alignment score")).toBeInTheDocument();
    expect(within(excluded).getByText(/It may still matter for the role/)).toBeInTheDocument();
  });

  it("never adds the badge to NOT_ASSESSABLE rows, which have their own section", () => {
    render(<ResultView result={excludedResult({ alignment: 0, assessable: 1 })} />);
    const section = screen.getByRole("region", { name: "Not assessable from GitHub" });
    expect(within(section).queryByText("Not counted in alignment score")).not.toBeInTheDocument();
  });

  it("states the score's scope and the excluded count in the headline", () => {
    render(<ResultView result={excludedResult({ alignment: 0, assessable: 1 })} />);
    const headline = screen.getByRole("region", { name: "GitHub Evidence Alignment" });
    expect(within(headline).getByText(/covers only requirements GitScore can check from GitHub evidence/)).toBeInTheDocument();
    expect(within(headline).getByText(/2 evaluated requirements are not counted/)).toBeInTheDocument();
  });

  it("keeps the no-eligible-requirement state as 'Not available', never 0", () => {
    render(<ResultView result={excludedResult({ alignment: null, assessable: 0 })} />);
    const headline = screen.getByRole("region", { name: "GitHub Evidence Alignment" });
    expect(within(headline).getByText("Not available")).toBeInTheDocument();
    expect(within(headline).queryByText("0")).not.toBeInTheDocument();
    expect(within(headline).getByText(/2 evaluated requirements are not counted/)).toBeInTheDocument();
  });

  it("shows no excluded-count note when nothing is excluded", () => {
    render(<ResultView result={makeAnalyzeResponse()} />);
    expect(screen.queryByText(/evaluated requirements? (is|are) not counted/)).not.toBeInTheDocument();
    expect(screen.queryByText("Not counted in alignment score")).not.toBeInTheDocument();
  });

  it("never uses penalty, irrelevance or missing-skill language for excluded rows", () => {
    const { container } = render(<ResultView result={excludedResult({ alignment: 0, assessable: 1 })} />);
    const text = container.textContent ?? "";
    for (const forbidden of [/penal/i, /irrelevant/i, /does not matter/i, /missing skill/i, /\bfailed\b/i, /lacks/i]) {
      const hits = text.match(forbidden) ?? [];
      // The approved NOT_OBSERVED section disclaimer says "...does not mean the
      // candidate lacks the skill" -- the one permitted negated use of "lacks".
      if (forbidden.source === "lacks") {
        expect(hits.length).toBeLessThanOrEqual(1);
      } else {
        expect(hits).toEqual([]);
      }
    }
  });
});
