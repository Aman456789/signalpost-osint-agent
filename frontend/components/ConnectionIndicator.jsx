const LABELS = { live: "Live", reconnecting: "Reconnecting", offline: "Offline" };

export function ConnectionIndicator({ state, onRetry }) {
  return (
    <span className="row" style={{ gap: 8 }}>
      <span className={`conn conn-${state}`} role="status">
        <span className="dot" aria-hidden="true" />
        {LABELS[state]}
      </span>
      {onRetry && (
        <button type="button" className="btn small" onClick={onRetry}>
          Reconnect
        </button>
      )}
    </span>
  );
}
