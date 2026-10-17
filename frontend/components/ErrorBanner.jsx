export function ErrorBanner({ message, onRetry }) {
  return (
    <div role="alert" className="error-banner">
      <span>{message}</span>
      {onRetry && (
        <button type="button" className="btn small" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}
