import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";

import { AlignmentHeadline } from "@/components/AlignmentHeadline";
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
      assessment: {
        github_evidence_alignment: null,
        assessable_requirement_count: 0,
        uninterpreted_requirement_count: 0,
        unparsed_claim_count: 0,
      },
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

  // -------------------------------------------------------------------
  // Milestone 9E Workstream C -- evidence repository links and
  // calibrated evidence-type descriptions
  // -------------------------------------------------------------------

  it("links each evidence repository to GitHub using only the API's own owner/name, never a fabricated or file-specific URL", () => {
    render(<ResultView result={makeAnalyzeResponse()} />);

    const links = screen.getAllByRole("link");
    expect(links.length).toBeGreaterThan(0);
    for (const link of links) {
      const href = link.getAttribute("href")!;
      // Repository root only -- never a /blob/<branch>/<path> deep link
      // (no default-branch fact exists to build one from safely).
      expect(href).toMatch(/^https:\/\/github\.com\/[^/]+\/[^/]+$/);
    }

    const dockerItem = screen.getByText("Familiarity with Docker").closest("li")!;
    const link = within(dockerItem).getByRole("link", { name: "octocat/api-service" });
    expect(link).toHaveAttribute("href", "https://github.com/octocat/api-service");
    // The Dockerfile path is still shown as plain text, never turned
    // into a (guessed-branch) link.
    expect(within(dockerItem).getByText(/— Dockerfile/)).toBeInTheDocument();
  });

  it("shows a calibrated, non-numeric description of what each evidence type represents", () => {
    render(<ResultView result={makeAnalyzeResponse()} />);

    const dockerItem = screen.getByText("Familiarity with Docker").closest("li")!;
    expect(
      within(dockerItem).getByText(/Docker\/containerization files present in the repository/),
    ).toBeInTheDocument();

    const supportedSection = screen.getByRole("heading", { name: "Supported by GitHub evidence" }).closest("section")!;
    const pythonItem = within(supportedSection)
      .getByText(/3\+ years of experience building Python backend services/)
      .closest("li")!;
    expect(
      within(pythonItem).getByText(/language composition/),
    ).toBeInTheDocument();
  });

  // -------------------------------------------------------------------
  // Milestone 9E Workstream B -- duplicate-looking requirement text is
  // disambiguated with a concept label, including across statuses.
  // -------------------------------------------------------------------

  it("appends a concept label to duplicate requirement text that appears under different, even contradictory, statuses", () => {
    const response = makeAnalyzeResponse({
      requirements: {
        supported: [
          makeRequirement({
            text: "Strong experience with Docker and Kubernetes",
            status: "supported",
            concept_id: "infra.docker",
            concept_label: "Docker",
            matched_concept_ids: ["infra.docker"],
            evidence: [
              {
                concept_id: "infra.docker",
                evidence_type: "docker",
                confidence: "strong",
                repository: { owner: "octocat", name: "infra-repo" },
                file_path: null,
                detail: "root file present: Dockerfile",
              },
            ],
          }),
        ],
        not_observed: [
          makeRequirement({
            text: "Strong experience with Docker and Kubernetes",
            status: "not_observed",
            concept_id: "infra.kubernetes",
            concept_label: "Kubernetes",
          }),
        ],
        not_assessable: [],
      },
    });
    render(<ResultView result={response} />);

    const supportedSection = screen.getByRole("heading", { name: "Supported by GitHub evidence" }).closest("section")!;
    const notObservedSection = screen
      .getByRole("heading", { name: "Not observed in analyzed GitHub evidence" })
      .closest("section")!;

    expect(
      within(supportedSection).getByText("Strong experience with Docker and Kubernetes (Docker)"),
    ).toBeInTheDocument();
    expect(
      within(notObservedSection).getByText("Strong experience with Docker and Kubernetes (Kubernetes)"),
    ).toBeInTheDocument();
    // Never the bare, ambiguous text once a label is available to
    // disambiguate it.
    expect(within(supportedSection).queryByText("Strong experience with Docker and Kubernetes")).not.toBeInTheDocument();
  });

  it("does not append a concept label to requirement text that is not duplicated anywhere in the result", () => {
    render(<ResultView result={makeAnalyzeResponse()} />);

    // "Familiarity with Docker" is unique across the whole fixture --
    // must render exactly as-is, no "(Docker)" appended.
    expect(screen.getByText("Familiarity with Docker")).toBeInTheDocument();
    expect(screen.queryByText("Familiarity with Docker (Docker)")).not.toBeInTheDocument();
  });

  it("does not append a label when a duplicate row has no concept_label to disambiguate with", () => {
    // "3+ years of experience building Python backend services" is
    // deliberately duplicated in the base fixture: once SUPPORTED
    // (language.python, concept_label "Python") and once NOT_ASSESSABLE
    // (a split non-technical experience claim, concept_label null).
    render(<ResultView result={makeAnalyzeResponse()} />);

    const notAssessableSection = screen.getByRole("heading", { name: "Not assessable from GitHub" }).closest("section")!;
    // The non-technical row has no concept to label -- rendered bare.
    expect(
      within(notAssessableSection).getByText("3+ years of experience building Python backend services"),
    ).toBeInTheDocument();
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
      assessment: {
        github_evidence_alignment: 67,
        assessable_requirement_count: 3,
        uninterpreted_requirement_count: 2,
        unparsed_claim_count: 0,
      },
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

  // -------------------------------------------------------------------
  // Milestone 9E Workstream A -- the second, separate unparsed-claims
  // headline caveat (never summed with the uninterpreted-requirement count)
  // -------------------------------------------------------------------

  it("shows the unparsed-claims headline caveat separately from the uninterpreted-requirement caveat", () => {
    const response = makeAnalyzeResponse({
      assessment: {
        github_evidence_alignment: 50,
        assessable_requirement_count: 2,
        uninterpreted_requirement_count: 1,
        unparsed_claim_count: 2,
      },
    });
    render(<ResultView result={response} />);

    expect(
      screen.getByText("1 requirement could not be confidently interpreted by GitScore's parser -- see below."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "2 additional statements in the job posting could not be parsed as a requirement at all -- see below.",
      ),
    ).toBeInTheDocument();
  });

  it("omits the unparsed-claims headline caveat when there are none", () => {
    render(<ResultView result={makeAnalyzeResponse()} />);
    expect(screen.queryByText(/could not be parsed as a requirement at all/)).not.toBeInTheDocument();
  });

  it("renders the unparsed-claims caveat using 'statements', never 'requirements' (not a confirmed requirement)", () => {
    const response = makeAnalyzeResponse({
      assessment: {
        github_evidence_alignment: 100,
        assessable_requirement_count: 1,
        uninterpreted_requirement_count: 0,
        unparsed_claim_count: 1,
      },
    });
    render(<ResultView result={response} />);

    const caveat = screen.getByText(/could not be parsed as a requirement at all/);
    expect(caveat.textContent).toContain("statement");
    expect(caveat.textContent).not.toMatch(/\brequirements\b/);
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

  // -------------------------------------------------------------------
  // Milestone 9G -- headline coverage-gap visibility
  // -------------------------------------------------------------------

  it("1. shows the coverage-gap badge and a concrete excerpt for a high-alignment result with an unparsed claim (karpathy x computer_vision_01)", () => {
    // Real values live-verified against the actual karpathy offline
    // fixture via the real running API (see MILESTONE_9F_REQUIREMENT_COVERAGE_DESIGN.md
    // Section 5.1) -- required 3/3, preferred 1/1, alignment 100,
    // uninterpreted_requirement_count 0, unparsed_claim_count 1, the
    // OpenCV claim. Reproduced here as an offline fixture; no live
    // GitHub or API call is made by this test.
    const response = makeAnalyzeResponse({
      assessment: {
        github_evidence_alignment: 100,
        assessable_requirement_count: 4,
        uninterpreted_requirement_count: 0,
        unparsed_claim_count: 1,
      },
      required: { supported: 3, assessable: 3 },
      preferred: { supported: 1, assessable: 1 },
      unparsed_claims: [{ text: "Experience with OpenCV for image processing" }],
    });
    render(<ResultView result={response} />);

    const headline = screen.getByRole("heading", { name: "GitHub Evidence Alignment" }).closest("section")!;
    expect(within(headline).getByText("100")).toBeInTheDocument();
    expect(within(headline).getByText("Known coverage gaps")).toBeInTheDocument();
    expect(
      within(headline).getByText('Potential requirement not interpreted: "Experience with OpenCV for image processing"'),
    ).toBeInTheDocument();
    expect(within(headline).getByText("This score excludes job-description text GitScore could not interpret.")).toBeInTheDocument();
  });

  it("2. shows the coverage-gap badge for a high-alignment result with only an uninterpreted placeholder (no unparsed claim text)", () => {
    const response = makeAnalyzeResponse({
      assessment: {
        github_evidence_alignment: 90,
        assessable_requirement_count: 9,
        uninterpreted_requirement_count: 2,
        unparsed_claim_count: 0,
      },
      unparsed_claims: [],
    });
    render(<ResultView result={response} />);

    const headline = screen.getByRole("heading", { name: "GitHub Evidence Alignment" }).closest("section")!;
    expect(within(headline).getByText("90")).toBeInTheDocument();
    expect(within(headline).getByText("Known coverage gaps")).toBeInTheDocument();
    expect(within(headline).getByText("This score excludes job-description text GitScore could not interpret.")).toBeInTheDocument();
    // No concrete example line -- there is no unparsed-claim text to quote.
    expect(within(headline).queryByText(/Potential requirement not interpreted/)).not.toBeInTheDocument();
    // The pre-existing, unchanged M9C caveat still renders.
    expect(
      within(headline).getByText("2 requirements could not be confidently interpreted by GitScore's parser -- see below."),
    ).toBeInTheDocument();
  });

  it("3. shows the badge once and both pre-existing caveats when both kinds of gaps are present simultaneously", () => {
    const response = makeAnalyzeResponse({
      assessment: {
        github_evidence_alignment: 60,
        assessable_requirement_count: 5,
        uninterpreted_requirement_count: 1,
        unparsed_claim_count: 2,
      },
      unparsed_claims: [{ text: "First unparsed statement" }, { text: "Second unparsed statement" }],
    });
    render(<ResultView result={response} />);

    const headline = screen.getByRole("heading", { name: "GitHub Evidence Alignment" }).closest("section")!;
    // Exactly one badge, not one per gap kind.
    expect(within(headline).getAllByText("Known coverage gaps")).toHaveLength(1);
    expect(
      within(headline).getByText('Potential requirement not interpreted: "First unparsed statement" (+1 more -- see below)'),
    ).toBeInTheDocument();
    expect(within(headline).queryByText(/Second unparsed statement/)).not.toBeInTheDocument();
    expect(
      within(headline).getByText("1 requirement could not be confidently interpreted by GitScore's parser -- see below."),
    ).toBeInTheDocument();
    expect(
      within(headline).getByText("2 additional statements in the job posting could not be parsed as a requirement at all -- see below."),
    ).toBeInTheDocument();
  });

  it("4. shows no badge, no excerpt, and no 'complete'/'fully analyzed' affirmation when no gaps are detected", () => {
    render(<ResultView result={makeAnalyzeResponse()} />);

    const headline = screen.getByRole("heading", { name: "GitHub Evidence Alignment" }).closest("section")!;
    expect(within(headline).queryByText("Known coverage gaps")).not.toBeInTheDocument();
    expect(within(headline).queryByText(/excludes job-description text/)).not.toBeInTheDocument();
    expect(within(headline).queryByText(/Potential requirement not interpreted/)).not.toBeInTheDocument();
    // Absence of a gap must never be rendered as a positive claim of
    // exhaustiveness (M9F Section 5.4).
    const text = headline.textContent ?? "";
    expect(text).not.toMatch(/\bComplete\b/);
    expect(text).not.toMatch(/Fully analyzed/i);
    expect(text).not.toMatch(/100% requirements interpreted/i);
  });

  it("5. shows the badge beside 'Not available' when alignment is null but a known gap exists (zero assessable requirements)", () => {
    const response = makeAnalyzeResponse({
      assessment: {
        github_evidence_alignment: null,
        assessable_requirement_count: 0,
        uninterpreted_requirement_count: 0,
        unparsed_claim_count: 1,
      },
      required: null,
      preferred: null,
      unparsed_claims: [{ text: "Experience with a totally novel, unregistered platform" }],
    });
    render(<ResultView result={response} />);

    const headline = screen.getByRole("heading", { name: "GitHub Evidence Alignment" }).closest("section")!;
    expect(within(headline).getByText("Not available")).toBeInTheDocument();
    expect(within(headline).getByText("Known coverage gaps")).toBeInTheDocument();
    expect(
      within(headline).getByText('Potential requirement not interpreted: "Experience with a totally novel, unregistered platform"'),
    ).toBeInTheDocument();
  });

  it("6. names only the first of several unparsed claims and shows an accurate '+N more' count", () => {
    const response = makeAnalyzeResponse({
      assessment: {
        github_evidence_alignment: 50,
        assessable_requirement_count: 2,
        uninterpreted_requirement_count: 0,
        unparsed_claim_count: 4,
      },
      unparsed_claims: [
        { text: "Claim one" },
        { text: "Claim two" },
        { text: "Claim three" },
        { text: "Claim four" },
      ],
    });
    render(<ResultView result={response} />);

    const headline = screen.getByRole("heading", { name: "GitHub Evidence Alignment" }).closest("section")!;
    expect(
      within(headline).getByText('Potential requirement not interpreted: "Claim one" (+3 more -- see below)'),
    ).toBeInTheDocument();
    for (const other of ["Claim two", "Claim three", "Claim four"]) {
      expect(within(headline).queryByText(new RegExp(other))).not.toBeInTheDocument();
    }
  });

  it("7. truncates a very long unparsed-claim excerpt in the headline while preserving the full text further down the page", () => {
    const longClaim =
      "Experience architecting, operating, and continuously improving a highly available, horizontally " +
      "scalable, multi-region distributed systems platform serving millions of daily active users worldwide";
    const response = makeAnalyzeResponse({
      assessment: {
        github_evidence_alignment: 80,
        assessable_requirement_count: 4,
        uninterpreted_requirement_count: 0,
        unparsed_claim_count: 1,
      },
      unparsed_claims: [{ text: longClaim }],
    });
    render(<ResultView result={response} />);

    const headline = screen.getByRole("heading", { name: "GitHub Evidence Alignment" }).closest("section")!;
    const headlineExcerpt = headline.querySelector(".alignment-coverage-gap-example")!.textContent!;
    expect(headlineExcerpt).not.toContain(longClaim);
    expect(headlineExcerpt).toContain("…");
    expect(headlineExcerpt.length).toBeLessThan(longClaim.length);

    // The full, untruncated original text is still shown verbatim in
    // the separate unparsed-claims section further down the page.
    const unparsedSection = screen
      .getByRole("heading", { name: "Statements GitScore could not parse as requirements" })
      .closest("section")!;
    expect(within(unparsedSection).getByText(longClaim)).toBeInTheDocument();
  });

  it("8. AlignmentHeadline renders safely with no coverage-gap props supplied at all (missing/empty diagnostics)", () => {
    render(<AlignmentHeadline alignment={42} />);

    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.queryByText("Known coverage gaps")).not.toBeInTheDocument();
    expect(screen.queryByText(/excludes job-description text/)).not.toBeInTheDocument();
  });

  it("9. never classifies an unparsed claim's own excerpt as 'required' or 'critical' (no criticality invented)", () => {
    const response = makeAnalyzeResponse({
      assessment: {
        github_evidence_alignment: 100,
        assessable_requirement_count: 3,
        uninterpreted_requirement_count: 0,
        unparsed_claim_count: 1,
      },
      unparsed_claims: [{ text: "Experience with OpenCV for image processing" }],
    });
    render(<ResultView result={response} />);

    const headline = screen.getByRole("heading", { name: "GitHub Evidence Alignment" }).closest("section")!;
    const excerptText = headline.querySelector(".alignment-coverage-gap-example")!.textContent!;
    expect(excerptText).not.toMatch(/\brequired\b/i);
    expect(excerptText).not.toMatch(/\bcritical\b/i);
    const badgeText = headline.querySelector(".coverage-gap-badge")!.textContent!;
    expect(badgeText).not.toMatch(/\brequired\b/i);
    expect(badgeText).not.toMatch(/\bcritical\b/i);
  });

  it("10. leaves the alignment score's own numerical value completely unchanged by the coverage-gap presentation", () => {
    const withoutGap = makeAnalyzeResponse({
      assessment: {
        github_evidence_alignment: 100,
        assessable_requirement_count: 4,
        uninterpreted_requirement_count: 0,
        unparsed_claim_count: 0,
      },
    });
    const withGap = makeAnalyzeResponse({
      assessment: {
        github_evidence_alignment: 100,
        assessable_requirement_count: 4,
        uninterpreted_requirement_count: 0,
        unparsed_claim_count: 1,
      },
      unparsed_claims: [{ text: "Experience with OpenCV for image processing" }],
    });

    const { unmount } = render(<ResultView result={withoutGap} />);
    expect(screen.getByText("100")).toBeInTheDocument();
    unmount();

    render(<ResultView result={withGap} />);
    expect(screen.getByText("100")).toBeInTheDocument();
  });
});
