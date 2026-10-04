import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";

import { ResultView } from "@/components/ResultView";
import { makeAnalyzeResponse, makeRequirement } from "@/test/fixtures";

// "candidate lacks"/"candidate does not know" are deliberately NOT in
// this list -- the approved NOT_OBSERVED disclaimer legitimately
// contains "...does not mean the candidate lacks the skill" as a
// negation; that exact sentence is pinned separately above.
const FORBIDDEN_WORDS = [
  /\bfailed\b/i,
  /missing skill/i,
  /unqualified/i,
  /\bhire\b/i,
  /\breject\b/i,
  /weakness/i,
];

describe("ResultView", () => {
  it("renders the alignment headline, required/preferred, and coverage (D/E/H)", () => {
    render(<ResultView result={makeAnalyzeResponse()} />);

    expect(screen.getByRole("heading", { name: "GitHub Evidence Alignment" })).toBeInTheDocument();
    expect(screen.getByText("40")).toBeInTheDocument();
    expect(screen.getByText("2 of 3 supported")).toBeInTheDocument();
    expect(screen.getByText("0 of 2 supported")).toBeInTheDocument();
    expect(screen.getByText("15 of 20 repositories deeply analyzed")).toBeInTheDocument();
  });

  it("renders null alignment as 'Not available', never 0/NaN/-1 (F)", () => {
    const response = makeAnalyzeResponse({
      assessment: { github_evidence_alignment: null, assessable_requirement_count: 0 },
    });
    render(<ResultView result={response} />);

    expect(screen.getByText("Not available")).toBeInTheDocument();
    expect(
      screen.getByText("No job requirements could be meaningfully assessed from GitHub evidence."),
    ).toBeInTheDocument();
    const alignmentSection = screen.getByRole("heading", { name: "GitHub Evidence Alignment" })
      .closest("section")!;
    expect(within(alignmentSection).queryByText("0")).not.toBeInTheDocument();
    expect(within(alignmentSection).queryByText("-1")).not.toBeInTheDocument();
    expect(within(alignmentSection).queryByText(/NaN/)).not.toBeInTheDocument();
  });

  it("renders null required/preferred with correct wording, never '0 of 0' (G)", () => {
    const response = makeAnalyzeResponse({ required: null, preferred: null });
    render(<ResultView result={response} />);

    expect(screen.getByText("No required requirements were assessable")).toBeInTheDocument();
    expect(screen.getByText("No preferred requirements were assessable")).toBeInTheDocument();
    expect(screen.queryByText("0 of 0 supported")).not.toBeInTheDocument();
  });

  it("renders the prioritization note when repository coverage is incomplete (I)", () => {
    render(<ResultView result={makeAnalyzeResponse()} />);

    expect(
      screen.getByText(
        "Highest-ranked repositories were prioritized; not every discovered repository was deeply analyzed.",
      ),
    ).toBeInTheDocument();
  });

  it("renders 'All N discovered repositories were deeply analyzed' when complete, with no percentage", () => {
    const response = makeAnalyzeResponse({
      repository_analysis: { discovered: 12, analyzed: 12, partially_analyzed: 0, complete: true },
    });
    render(<ResultView result={response} />);

    expect(screen.getByText("All 12 discovered repositories were deeply analyzed.")).toBeInTheDocument();
    const coverageSection = screen.getByRole("heading", { name: "Repository analysis" }).closest("section")!;
    expect(within(coverageSection).queryByText(/%/)).not.toBeInTheDocument();
  });

  it("renders supported requirements with evidence (J/K)", () => {
    render(<ResultView result={makeAnalyzeResponse()} />);

    const supportedSection = screen.getByRole("heading", { name: "Supported by GitHub evidence" })
      .closest("section")!;
    const dockerItem = within(supportedSection).getByText("Familiarity with Docker").closest("li")!;
    expect(within(dockerItem).getAllByText("octocat/api-service").length).toBeGreaterThan(0);
    expect(within(dockerItem).getByText(/— Dockerfile/)).toBeInTheDocument();
    expect(within(dockerItem).getByText(/Strong confidence/)).toBeInTheDocument();
  });

  it("uses neutral NOT_OBSERVED wording, never implying the candidate lacks the skill (L)", () => {
    render(<ResultView result={makeAnalyzeResponse()} />);

    const section = screen.getByRole("heading", { name: "Not observed in analyzed GitHub evidence" })
      .closest("section")!;
    expect(
      within(section).getByText(
        "No supporting evidence was observed in the analyzed GitHub material. This does not mean the candidate lacks the skill.",
      ),
    ).toBeInTheDocument();
    expect(within(section).getByText("Experience with PostgreSQL")).toBeInTheDocument();
  });

  it("uses neutral NOT_ASSESSABLE wording, never framed as a failure (M)", () => {
    render(<ResultView result={makeAnalyzeResponse()} />);

    const section = screen.getByRole("heading", { name: "Not assessable from GitHub" }).closest("section")!;
    expect(
      within(section).getByText("GitHub evidence cannot reliably establish these requirements."),
    ).toBeInTheDocument();
    expect(within(section).getByText("Excellent written and verbal communication")).toBeInTheDocument();
  });

  it("renders diagnostics secondarily, after the requirement sections (T)", () => {
    render(<ResultView result={makeAnalyzeResponse()} />);

    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    const notAssessableIndex = headings.indexOf("Not assessable from GitHub");
    const detailsSummary = screen.getByText("Analysis details");

    expect(notAssessableIndex).toBeGreaterThanOrEqual(0);
    // Diagnostics is a <details><summary>, not an h2 -- confirm it renders
    // after every requirement-group heading in document order.
    const allHeadingEls = screen.getAllByRole("heading", { level: 2 });
    const lastHeading = allHeadingEls[allHeadingEls.length - 1]!;
    expect(lastHeading.compareDocumentPosition(detailsSummary) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("shows a modest warning (not an error) when extraction failures occurred", () => {
    const response = makeAnalyzeResponse({
      diagnostics: { extraction_failure_count: 2, unknown_dependency_count: 0 },
      repository_analysis: { discovered: 20, analyzed: 15, partially_analyzed: 1, complete: false },
    });
    render(<ResultView result={response} />);

    expect(screen.getByText(/Some repository evidence could not be analyzed/)).toBeInTheDocument();
    expect(screen.queryByText(/analysis failed/i)).not.toBeInTheDocument();
  });

  it("renders 'None.' for an empty requirement group instead of hiding the section", () => {
    const response = makeAnalyzeResponse({
      requirements: { supported: [], not_observed: [], not_assessable: [makeRequirement({ status: "not_assessable" })] },
    });
    render(<ResultView result={response} />);

    expect(screen.getByRole("heading", { name: "Supported by GitHub evidence" })).toBeInTheDocument();
    const supportedSection = screen.getByRole("heading", { name: "Supported by GitHub evidence" })
      .closest("section")!;
    expect(within(supportedSection).getByText("None.")).toBeInTheDocument();
  });

  it("never uses hire/reject/missing-skill language anywhere in a full result (U)", () => {
    render(<ResultView result={makeAnalyzeResponse()} />);

    const text = document.body.textContent ?? "";
    for (const forbidden of FORBIDDEN_WORDS) {
      expect(text).not.toMatch(forbidden);
    }
  });

  it("never fabricates a repository URL or file URL not present in the API response", () => {
    render(<ResultView result={makeAnalyzeResponse()} />);

    const links = screen.queryAllByRole("link");
    expect(links).toHaveLength(0);
  });
});
