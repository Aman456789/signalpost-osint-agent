import { LIMITS } from "@/lib/api";
import { formatNumber } from "@/lib/format";

export function BudgetBar({ total, softCap = LIMITS.softCap, brake = LIMITS.brake, max = LIMITS.maxRequests }) {
  const place = (value) => `${(Math.min(value, max) * 100) / max}%`;
  const tone = total >= brake ? "danger" : total >= softCap ? "warn" : "ok";
  return (
    <div className="stack" style={{ gap: 6 }}>
      <div
        className="budget-bar"
        role="progressbar"
        aria-label="Outbound requests"
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={total}
        aria-valuetext={`${formatNumber(total)} of ${formatNumber(max)} requests`}
      >
        <div className={`budget-fill ${tone}`} style={{ width: place(total) }} />
        <span className="budget-marker" data-marker="soft" style={{ left: place(softCap) }} />
        <span className="budget-marker" data-marker="brake" style={{ left: place(brake) }} />
      </div>
      <div className="budget-legend">
        <span>Soft cap {formatNumber(softCap)}</span>
        <span>Brake {formatNumber(brake)}</span>
        <span>Maximum {formatNumber(max)}</span>
      </div>
    </div>
  );
}
