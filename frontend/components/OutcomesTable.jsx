import { StatusBadge } from "@/components/StatusBadge";
import { formatNumber } from "@/lib/format";

const ORDER = ["published", "registry_only", "not_found", "registry_unavailable", "not_processed_budget", "failed"];

function percent(count, total) {
  return total > 0 ? `${((count * 100) / total).toFixed(1)}%` : "–";
}

// noWebsite is the number of companies flagged no_website; they are a subset of registry_only
export function OutcomesTable({ outcomes, total, noWebsite }) {
  const statuses = [
    ...ORDER.filter((status) => (outcomes[status] ?? 0) > 0 || status === "registry_only"),
    ...Object.keys(outcomes).filter((status) => !ORDER.includes(status) && outcomes[status] > 0),
  ];

  return (
    <table className="data">
      <caption className="visually-hidden">Companies by processing status</caption>
      <thead>
        <tr>
          <th scope="col">Status</th>
          <th scope="col" className="right">Companies</th>
          <th scope="col" className="right">Share of input</th>
        </tr>
      </thead>
      <tbody>
        {statuses.map((status) => {
          const count = outcomes[status] ?? 0;
          return (
            <tr key={status}>
              <th scope="row">
                <StatusBadge status={status} />
                {status === "registry_only" && (
                  <div className="subline">of which flagged no_website: {noWebsite ?? "not available"}</div>
                )}
              </th>
              <td className="right">{formatNumber(count)}</td>
              <td className="right">{percent(count, total)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
