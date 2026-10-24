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
      assessment: { github_evidence_alignment: null, assessable_requirement_count: 0, uninterpreted_requirement_count: 0 },
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

  // -------------------------------------------------------------------
  // Milestone 9C
  // -------------------------------------------------------------------

  it("splits not_assessable into two distinctly-worded subsections", () => {
    const response = makeAnalyzeResponse({
      requirements: {
        supported: [],
        not_observed: [],
        not_assessable: [
          makeRequirement({
            text: "Bachelor's degree in Computer Science",
            status: "not_assessable",
            concept_id: null,
            category: "education",
            interpretation_status: "non_technical",
          }),
          makeRequirement({
            text: "Experience with Terraform",
            status: "not_assessable",
            concept_id: null,
            category: "unresolved_requirement",
            interpretation_status: "unparsed_placeholder",
          }),
        ],
      },
    });
    render(<ResultView result={response} />);

    const outerSection = screen.getByRole("heading", { name: "Not assessable from GitHub" }).closest("section")!;
    const nonTechHeading = within(outerSection).getByRole("heading", { name: "Genuinely non-technical requirements" });
    const placeholderHeading = within(outerSection).getByRole("heading", { name: "Could not be confidently interpreted" });

    const nonTechSubsection = nonTechHeading.closest(".requirement-subsection") as HTMLElement;
    const placeholderSubsection = placeholderHeading.closest(".requirement-subsection") as HTMLElement;

    expect(within(nonTechSubsection).getByText("Bachelor's degree in Computer Science")).toBeInTheDocument();
    expect(within(nonTechSubsection).queryByText("Experience with Terraform")).not.toBeInTheDocument();

    expect(within(placeholderSubsection).getByText("Experience with Terraform")).toBeInTheDocument();
    expect(within(placeholderSubsection).queryByText("Bachelor's degree in Computer Science")).not.toBeInTheDocument();

    // The two subsections must never share identical explanatory
    // wording -- one is a fact about the posting, the other about
    // GitScore's own parser.
    expect(
      within(placeholderSubsection).getByText(/GitScore's own parser could not confidently interpret/),
    ).toBeInTheDocument();
    expect(
      within(nonTechSubsection).queryByText(/GitScore's own parser could not confidently interpret/),
    ).not.toBeInTheDocument();
  });

  it("shows the headline caveat when requirements could not be confidently interpreted", () => {
    const response = makeAnalyzeResponse({
      assessment: { github_evidence_alignment: 67, assessable_requirement_count: 3, uninterpreted_requirement_count: 2 },
    });
    render(<ResultView result={response} />);

    expect(
      screen.getByText("2 requirements could not be confidently interpreted by GitScore's parser -- see below."),
    ).toBeInTheDocument();
  });

  it("omits the headline caveat entirely when nothing was uninterpreted", () => {
    render(<ResultView result={makeAnalyzeResponse()} />);
    expect(screen.queryByText(/could not be confidently interpreted by GitScore's parser/)).not.toBeInTheDocument();
  });

  it("renders the unparsed-claims section with raw text and no status/evidence", () => {
    const response = makeAnalyzeResponse({
      unparsed_claims: [{ text: "Experience designing distributed systems" }],
    });
    render(<ResultView result={response} />);

    const section = screen
      .getByRole("heading", { name: "Statements GitScore could not parse as requirements" })
      .closest("section")!;
    expect(within(section).getByText("Experience designing distributed systems")).toBeInTheDocument();
  });

  it("omits the unparsed-claims section entirely when there are none (the normal case)", () => {
    render(<ResultView result={makeAnalyzeResponse()} />);
    expect(
      screen.queryByRole("heading", { name: "Statements GitScore could not parse as requirements" }),
    ).not.toBeInTheDocument();
  });

  it("renders the unparsed-claims section after not_assessable and before diagnostics", () => {
    const response = makeAnalyzeResponse({
      unparsed_claims: [{ text: "Experience designing distributed systems" }],
    });
    render(<ResultView result={response} />);

    const notAssessableHeading = screen.getByRole("heading", { name: "Not assessable from GitHub" });
    const unparsedHeading = screen.getByRole("heading", { name: "Statements GitScore could not parse as requirements" });
    const detailsSummary = screen.getByText("Analysis details");

    expect(notAssessableHeading.compareDocumentPosition(unparsedHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(unparsedHeading.compareDocumentPosition(detailsSummary) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});
