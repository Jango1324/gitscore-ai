export function LoadingNotice() {
  return (
    <div className="loading-notice" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>Analyzing GitHub evidence…</span>
    </div>
  );
}
