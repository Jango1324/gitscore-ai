import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AnalyzePage } from "@/components/AnalyzePage";
import { makeAnalyzeResponse } from "@/test/fixtures";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("GitHub username"), "octocat");
  await user.type(screen.getByLabelText("Job description"), "Requirements:\n- Experience with Docker\n");
}

describe("AnalyzePage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("renders the form (A)", () => {
    render(<AnalyzePage />);

    expect(screen.getByLabelText("GitHub username")).toBeInTheDocument();
    expect(screen.getByLabelText("Job description")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyze GitHub Evidence" })).toBeInTheDocument();
  });

  it("rejects blank required fields without calling the API (B)", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const user = userEvent.setup();
    render(<AnalyzePage />);

    await user.click(screen.getByRole("button", { name: "Analyze GitHub Evidence" }));

    expect(await screen.findByText("GitHub username is required.")).toBeInTheDocument();
    expect(screen.getByText("Job description is required.")).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("rejects an oversized username without calling the API (C)", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const user = userEvent.setup();
    render(<AnalyzePage />);

    await user.type(screen.getByLabelText("GitHub username"), "x".repeat(40));
    await user.type(screen.getByLabelText("Job description"), "Requirements:\n- Docker\n");
    await user.click(screen.getByRole("button", { name: "Analyze GitHub Evidence" }));

    expect(await screen.findByText(/39 characters or fewer/)).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("shows a loading state and disables the submit button while the request is in flight (N/O)", async () => {
    let resolveFetch!: (value: Response) => void;
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>((resolve) => (resolveFetch = resolve))),
    );
    const user = userEvent.setup();
    render(<AnalyzePage />);
    await fillValidForm(user);

    await user.click(screen.getByRole("button", { name: "Analyze GitHub Evidence" }));

    expect(screen.getByText("Analyzing GitHub evidence…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyzing…" })).toBeDisabled();

    resolveFetch(jsonResponse(200, makeAnalyzeResponse()));
    await waitFor(() => expect(screen.queryByText("Analyzing GitHub evidence…")).not.toBeInTheDocument());
  });

  it("renders a successful response end-to-end (D/E)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(200, makeAnalyzeResponse())));
    const user = userEvent.setup();
    render(<AnalyzePage />);
    await fillValidForm(user);

    await user.click(screen.getByRole("button", { name: "Analyze GitHub Evidence" }));

    expect(await screen.findByRole("heading", { name: "GitHub Evidence Alignment" })).toBeInTheDocument();
    expect(screen.getByText("40")).toBeInTheDocument();
    expect(screen.getByText("2 of 3 supported")).toBeInTheDocument();
  });

  it("renders the github_user_not_found error message, not retryable (P)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(404, {
          error: {
            code: "github_user_not_found",
            message: "The requested GitHub user could not be found.",
            retryable: false,
          },
        }),
      ),
    );
    const user = userEvent.setup();
    render(<AnalyzePage />);
    await fillValidForm(user);

    await user.click(screen.getByRole("button", { name: "Analyze GitHub Evidence" }));

    expect(await screen.findByText("The requested GitHub user could not be found.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  });

  it("renders a retryable upstream error with a Try again action (Q)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(503, {
          error: {
            code: "github_rate_limited",
            message: "GitScore's GitHub API quota is temporarily exhausted. Please try again later.",
            retryable: true,
          },
        }),
      ),
    );
    const user = userEvent.setup();
    render(<AnalyzePage />);
    await fillValidForm(user);

    await user.click(screen.getByRole("button", { name: "Analyze GitHub Evidence" }));

    expect(
      await screen.findByText("GitScore's GitHub API quota is temporarily exhausted. Please try again later."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("renders a generic message for an unexpected server error, no internals leaked (R)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse(500, {
          error: { code: "internal_error", message: "An unexpected internal error occurred.", retryable: false },
        }),
      ),
    );
    const user = userEvent.setup();
    render(<AnalyzePage />);
    await fillValidForm(user);

    await user.click(screen.getByRole("button", { name: "Analyze GitHub Evidence" }));

    expect(await screen.findByText("An unexpected internal error occurred.")).toBeInTheDocument();
    expect(screen.queryByText(/Traceback/)).not.toBeInTheDocument();
    expect(screen.queryByText(/at analyzeJob/)).not.toBeInTheDocument();
  });

  it("renders a network-failure message when the API is unreachable (S)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );
    const user = userEvent.setup();
    render(<AnalyzePage />);
    await fillValidForm(user);

    await user.click(screen.getByRole("button", { name: "Analyze GitHub Evidence" }));

    expect(
      await screen.findByText("Could not reach the GitScore API. Check that the backend is running."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("retries the same request when Try again is clicked", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(503, {
          error: { code: "github_unavailable", message: "GitHub is temporarily unreachable.", retryable: true },
        }),
      )
      .mockResolvedValueOnce(jsonResponse(200, makeAnalyzeResponse()));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AnalyzePage />);
    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: "Analyze GitHub Evidence" }));
    await screen.findByRole("button", { name: "Try again" });

    await user.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByRole("heading", { name: "GitHub Evidence Alignment" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
