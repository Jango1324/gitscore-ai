/**
 * Milestone 8B -- the one typed client for `gitscore.api`.
 *
 * Renderer/client only: this file sends the exact `AnalyzeRequest` shape
 * to `POST /api/v1/analyze` and returns the exact `AnalyzeResponse` shape
 * -- no GitScore analysis logic is reproduced here.
 */
import type { AnalyzeRequest, AnalyzeResponse, ErrorResponse } from "@/types/api";

const DEFAULT_API_BASE_URL = "http://localhost:8000";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_GITSCORE_API_URL ?? DEFAULT_API_BASE_URL;

/** One structured error from the API's own `{"error": {...}}` envelope. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly retryable: boolean;

  constructor(status: number, code: string, message: string, retryable: boolean) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.retryable = retryable;
  }
}

/** The request never reached the API at all (offline, DNS, CORS, the
 * backend process isn't running, ...) -- distinct from `ApiError`,
 * which means the API responded but reported a failure. */
export class NetworkError extends Error {
  constructor(message = "Could not reach the GitScore API. Check that the backend is running.") {
    super(message);
    this.name = "NetworkError";
  }
}

async function parseErrorBody(response: Response): Promise<ErrorResponse["error"] | null> {
  try {
    const body = (await response.json()) as unknown;
    if (
      body !== null &&
      typeof body === "object" &&
      "error" in body &&
      typeof (body as ErrorResponse).error === "object"
    ) {
      return (body as ErrorResponse).error;
    }
  } catch {
    // Non-JSON or malformed body -- fall through to the generic error below.
  }
  return null;
}

export async function analyzeJob(
  request: AnalyzeRequest,
  options?: { signal?: AbortSignal },
): Promise<AnalyzeResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      signal: options?.signal,
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") {
      throw cause;
    }
    throw new NetworkError();
  }

  if (!response.ok) {
    const errorDetail = await parseErrorBody(response);
    throw new ApiError(
      response.status,
      errorDetail?.code ?? "unknown_error",
      errorDetail?.message ?? "An unexpected error occurred.",
      errorDetail?.retryable ?? false,
    );
  }

  return (await response.json()) as AnalyzeResponse;
}
