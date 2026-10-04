"use client";

import { useRef, useState } from "react";

import type { AnalyzeRequest, AnalyzeResponse } from "@/types/api";
import { analyzeJob, ApiError, NetworkError } from "@/lib/api";
import { AnalyzeForm } from "@/components/AnalyzeForm";
import { ResultView } from "@/components/ResultView";
import { ErrorBanner } from "@/components/ErrorBanner";
import { LoadingNotice } from "@/components/LoadingNotice";

type Status = "idle" | "loading" | "success" | "error";

interface ErrorState {
  message: string;
  retryable: boolean;
}

/**
 * Simple four-state model (idle/loading/success/error) -- no
 * Redux/Zustand; a single-page MVP form+result flow does not need a
 * global state-management framework (Milestone 8B Part 21).
 */
export function AnalyzePage() {
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<ErrorState | null>(null);
  const lastRequestRef = useRef<AnalyzeRequest | null>(null);

  async function runAnalysis(request: AnalyzeRequest) {
    lastRequestRef.current = request;
    setStatus("loading");
    setError(null);
    try {
      const response = await analyzeJob(request);
      setResult(response);
      setStatus("success");
    } catch (cause) {
      if (cause instanceof ApiError) {
        setError({ message: cause.message, retryable: cause.retryable });
      } else if (cause instanceof NetworkError) {
        setError({ message: cause.message, retryable: true });
      } else {
        setError({ message: "An unexpected error occurred.", retryable: false });
      }
      setStatus("error");
    }
  }

  function handleRetry() {
    const lastRequest = lastRequestRef.current;
    if (lastRequest) {
      void runAnalysis(lastRequest);
    }
  }

  const isLoading = status === "loading";

  return (
    <div className="analyze-page">
      <AnalyzeForm isLoading={isLoading} onSubmit={(request) => void runAnalysis(request)} />

      {status === "loading" && <LoadingNotice />}
      {status === "error" && error && (
        <ErrorBanner message={error.message} retryable={error.retryable} onRetry={handleRetry} />
      )}
      {status === "success" && result && <ResultView result={result} />}
    </div>
  );
}
