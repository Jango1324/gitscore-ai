interface ErrorBannerProps {
  message: string;
  retryable: boolean;
  onRetry: () => void;
}

/**
 * Renders the API's own safe, user-facing error message (or the
 * frontend's own NetworkError message) -- never a stack trace, raw
 * exception name, or internal code path.
 */
export function ErrorBanner({ message, retryable, onRetry }: ErrorBannerProps) {
  return (
    <div className="error-banner" role="alert">
      <p>{message}</p>
      {retryable && (
        <button type="button" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}
