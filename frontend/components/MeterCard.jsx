// ratio is 0 to 1 and adds a simple bar
export function MeterCard({ label, value, hint, ratio, children }) {
  const share = ratio === undefined || Number.isNaN(ratio) ? null : Math.min(ratio, 1);
  const tone = share === null ? "ok" : share >= 1 ? "danger" : share >= 0.85 ? "warn" : "ok";
  return (
    <section className="meter-card" aria-label={label}>
      <h3 className="meter-label">{label}</h3>
      <p className="meter-value">{value}</p>
      {share !== null && (
        <div className="bar" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(share * 100)}>
          <div className={`bar-fill ${tone}`} style={{ width: `${share * 100}%` }} />
        </div>
      )}
      {children}
      {hint && <p className="meter-hint">{hint}</p>}
    </section>
  );
}
