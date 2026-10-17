"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect } from "react";
import { BudgetBar } from "@/components/BudgetBar";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBanner } from "@/components/ErrorBanner";
import { HashText } from "@/components/HashText";
import { MeterCard } from "@/components/MeterCard";
import { OutcomesTable } from "@/components/OutcomesTable";
import { StatusBadge } from "@/components/StatusBadge";
import { getBudget, getReport, isFinished, listDossiers } from "@/lib/api";
import { formatDateTime, formatDuration, formatNumber, humanize } from "@/lib/format";
import { useLoad } from "@/lib/hooks";
import { useJob } from "@/lib/job-context";

// no_website is a flag, so it is counted from the per-company flags of registry_only dossiers.
async function countNoWebsite() {
  try {
    let count = 0;
    let cursor = null;
    do {
      const page = await listDossiers({ status: "registry_only", limit: 200, cursor });
      count += page.items.filter((d) => d.flags.includes("no_website")).length;
      cursor = page.next_cursor;
    } while (cursor);
    return count;
  } catch {
    return null;
  }
}

async function load(jobId) {
  const [report, budget] = await Promise.all([getReport(jobId), getBudget(jobId)]);
  return { report, budget, noWebsite: await countNoWebsite() };
}

function exportJson(report) {
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "run_report.json";
  link.click();
  URL.revokeObjectURL(url);
}

const yesNo = (value) => (value ? "Yes" : "No");

function Row({ label, children }) {
  return (
    <tr>
      <th scope="row">{label}</th>
      <td className="right">{children}</td>
    </tr>
  );
}

export default function ReportPage() {
  const { jobId } = useParams();
  const { job } = useJob();
  const { data, error, loading, reload } = useLoad(() => load(jobId), [jobId]);

  const finished = job?.job_id === jobId && isFinished(job);
  useEffect(() => {
    if (finished) reload();
  }, [finished, reload]);

  if (loading) return <p role="status" className="muted">Loading report…</p>;
  if (error?.status === 409) {
    return (
      <EmptyState title="Report available when the job finishes" action={<button type="button" className="btn" onClick={reload}>Check again</button>}>
        The run report is written once the job has finished.
      </EmptyState>
    );
  }
  if (error?.status === 404) return <EmptyState title="No report for this job">This job ended without a run report.</EmptyState>;
  if (error || !data) return <ErrorBanner message={error?.message ?? "The report could not be loaded."} onRetry={reload} />;

  const { report, budget, noWebsite } = data;
  const rejectionTotal = Object.values(report.rejections_by_reason).reduce((sum, n) => sum + n, 0);
  const limits = `${report.time_limit_min ?? "no"} min, ${formatNumber(budget.max_requests)} requests, $${Number(report.cost_limit_usd)}`;

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1 className="page-title">Run Report</h1>
        <button type="button" className="btn" onClick={() => exportJson(report)}>Export JSON</button>
      </div>

      <section className="panel stack" aria-labelledby="summary-heading">
        <h2 id="summary-heading">Job summary</h2>
        <p>
          Stop reason: <StatusBadge status={report.stop_reason} />
        </p>
        <table className="data">
          <caption className="visually-hidden">Job summary</caption>
          <tbody>
            <Row label="Job"><span className="mono">{report.job_id}</span></Row>
            <Row label="Mode">{`${humanize(report.mode)} (${limits})`}</Row>
            <Row label="Started">{formatDateTime(report.started_at)}</Row>
            <Row label="Ended">{formatDateTime(report.ended_at)}</Row>
            <Row label="Duration">{formatDuration(report.duration_seconds)}</Row>
            <Row label="Companies">{formatNumber(report.company_count)}</Row>
          </tbody>
        </table>
      </section>

      <section className="panel stack" aria-labelledby="outcomes-heading">
        <h2 id="outcomes-heading">Outcomes</h2>
        <OutcomesTable outcomes={report.outcomes} total={report.company_count} noWebsite={noWebsite} />
      </section>

      <section className="panel stack" aria-labelledby="budget-heading">
        <h2 id="budget-heading">Budget</h2>
        <MeterCard label="Outbound requests" value={`${formatNumber(report.requests.total)} of ${formatNumber(budget.max_requests)}`}>
          <BudgetBar total={report.requests.total} softCap={budget.soft_cap} brake={budget.brake} max={budget.max_requests} />
        </MeterCard>
        <table className="data">
          <caption className="visually-hidden">Requests by kind</caption>
          <tbody>
            {Object.entries(report.requests.by_kind).map(([kind, count]) => (
              <Row key={kind} label={humanize(kind)}>{formatNumber(count)}</Row>
            ))}
            <Row label="Remaining to soft cap">{formatNumber(Math.max(0, budget.soft_cap - report.requests.total))}</Row>
            <Row label="Remaining to brake">{formatNumber(Math.max(0, budget.brake - report.requests.total))}</Row>
            <Row label="Plan B used">{formatNumber(report.plan_b_used_count)}</Row>
          </tbody>
        </table>
      </section>

      <section className="panel stack" aria-labelledby="llm-heading">
        <h2 id="llm-heading">LLM</h2>
        <table className="data">
          <caption className="visually-hidden">LLM usage</caption>
          <tbody>
            <Row label="Calls">{formatNumber(report.llm_calls)}</Row>
            <Row label="Input tokens">{formatNumber(report.input_tokens)}</Row>
            <Row label="Output tokens">{formatNumber(report.output_tokens)}</Row>
            <Row label="Estimated cost">{`$${report.estimated_cost_usd}`}</Row>
            <Row label="Cost limit">{`$${Number(report.cost_limit_usd)}`}</Row>
          </tbody>
        </table>
      </section>

      <section className="panel stack" aria-labelledby="flags-heading">
        <h2 id="flags-heading">Flags</h2>
        <table className="data">
          <caption className="visually-hidden">Run flags</caption>
          <tbody>
            <Row label="Soft cap reached">{yesNo(report.flags.soft_cap_reached)}</Row>
            <Row label="Brake tripped">{yesNo(report.flags.brake_tripped)}</Row>
            <Row label="Kill switch tripped">{yesNo(report.flags.kill_switch_tripped)}</Row>
            <Row label="Registry outage detected">{yesNo(report.flags.plan_a_outage_detected)}</Row>
            <Row label="Plan B used">{formatNumber(report.plan_b_used_count)}</Row>
          </tbody>
        </table>
      </section>

      <section className="panel stack" aria-labelledby="rejections-heading">
        <h2 id="rejections-heading">Rejections</h2>
        {rejectionTotal === 0 ? (
          <p className="muted">No rejections in this run.</p>
        ) : (
          <>
            <p>{formatNumber(rejectionTotal)} rejected in total.</p>
            <ul>
              {Object.entries(report.rejections_by_reason).map(([reason, count]) => (
                <li key={reason}>
                  <Link href={`/rejections?reason=${reason}&job_id=${report.job_id}`}>{humanize(reason)}</Link>: {formatNumber(count)}
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section className="panel stack" aria-labelledby="checkpoint-heading">
        <h2 id="checkpoint-heading">Checkpoint</h2>
        <dl className="dl">
          <dt>File</dt><dd className="mono">{report.checkpoint?.path ?? "–"}</dd>
          <dt>Event sequence</dt><dd>{report.checkpoint?.sequence ?? "–"}</dd>
          <dt>Config hash</dt><dd><HashText value={report.config_hash} label="config hash" /></dd>
          <dt>Code version</dt><dd className="mono">{report.code_version}</dd>
        </dl>
      </section>
    </>
  );
}
