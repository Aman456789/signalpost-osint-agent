"use client";

import Link from "next/link";
import { useState } from "react";
import { BudgetBar } from "@/components/BudgetBar";
import { ErrorBanner } from "@/components/ErrorBanner";
import { MeterCard } from "@/components/MeterCard";
import { StatusBadge } from "@/components/StatusBadge";
import { LIMITS, errorMessage, getBudget, isFinished, startJob, validateInputs } from "@/lib/api";
import { formatDuration, formatNumber } from "@/lib/format";
import { useLoad } from "@/lib/hooks";
import { useJob } from "@/lib/job-context";

const MAX_FILE_BYTES = 1_000_000;
const SHOWN_REJECTED = 20;
const REASONS = {
  length_not_9: "Not 9 digits",
  non_digit: "Contains characters other than digits",
  mod11_checksum_failed: "MOD-11 checksum failed",
};

export default function CommandCenterPage() {
  const { job, budget: jobBudget, health, trackJob } = useJob();
  const idleBudget = useLoad(() => getBudget(), []);
  const [text, setText] = useState("");
  const [checked, setChecked] = useState(null); // { text, result }
  const [validating, setValidating] = useState(false);
  const [starting, setStarting] = useState(false);
  const [started, setStarted] = useState(null);
  const [error, setError] = useState(null);

  const budget = jobBudget ?? idleBudget.data;
  const running = job !== null && !isFinished(job);
  const nothingValid = checked?.text === text && checked.result.accepted.length === 0;

  async function validate(value) {
    if (!value.trim()) {
      setChecked(null);
      return null;
    }
    setValidating(true);
    setError(null);
    try {
      const result = await validateInputs(value);
      setChecked({ text: value, result });
      return result;
    } catch (err) {
      setError(errorMessage(err));
      return null;
    } finally {
      setValidating(false);
    }
  }

  async function start() {
    setStarting(true);
    const result = checked?.text === text ? checked.result : await validate(text);
    if (!result || result.accepted.length === 0) {
      setStarting(false);
      return;
    }
    try {
      const created = await startJob(result.accepted);
      setStarted(created);
      trackJob(created.job_id);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setStarting(false);
    }
  }

  async function onFile(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (file.size > MAX_FILE_BYTES) {
      setError("The file is larger than 1 MB.");
      return;
    }
    const content = await file.text();
    setText(content);
    void validate(content);
  }

  return (
    <>
      <h1 className="page-title">Command Center</h1>
      <p className="muted">Paste or upload Norwegian organisation numbers, check them, then start a job.</p>

      {health && health.status !== "ok" && (
        <ErrorBanner message={`The service reports a configuration problem: ${health.config.errors.join("; ") || "see /api/health"}`} />
      )}
      {health && !health.dependencies.llm.configured && (
        <p role="status" className="muted">LLM settings are missing in .env, so AI facts cannot be produced.</p>
      )}

      <section className="panel stack" aria-labelledby="input-heading">
        <h2 id="input-heading">Input</h2>
        <label htmlFor="orgnrs">Organisation numbers</label>
        <textarea
          id="orgnrs"
          className="input mono"
          rows={8}
          value={text}
          placeholder="One 9-digit number per line. Commas and semicolons also work."
          onChange={(e) => setText(e.target.value)}
          onBlur={(e) => { if (checked?.text !== e.target.value) void validate(e.target.value); }}
          onPaste={(e) => {
            const field = e.currentTarget;
            setTimeout(() => void validate(field.value), 0);
          }}
        />
        <input type="file" accept=".txt,.csv,text/plain,text/csv" aria-label="Upload a .txt or .csv file" onChange={onFile} />

        <div aria-live="polite" className="stack">
          {validating && <p className="muted">Checking…</p>}
          {checked && !validating && <ValidationSummary result={checked.result} />}
        </div>
        {error && <ErrorBanner message={error} onRetry={() => void validate(text)} />}

        <div className="row">
          <button
            type="button"
            className="btn primary"
            onClick={start}
            disabled={starting || validating || !text.trim() || nothingValid || running}
          >
            Start job
          </button>
          {running && <span className="muted">A job is already running.</span>}
        </div>
      </section>

      {started && (
        <section className="panel stack" aria-labelledby="started-heading">
          <h2 id="started-heading">Job started</h2>
          <p>
            Job <span className="mono">{started.job_id}</span> accepted {started.accepted_count} organisation numbers
            {started.replayed ? " (this request had already been started)" : ""}.
          </p>
          {job && <p>Status: <StatusBadge status={job.status} /></p>}
          <p>
            <Link href={`/jobs/${started.job_id}/terminal`}>Open Live Terminal</Link>
            {" · "}
            <Link href={`/jobs/${started.job_id}/report`}>Open Run Report</Link>
          </p>
        </section>
      )}

      <section className="stack" aria-labelledby="meters-heading">
        <h2 id="meters-heading">Run meters</h2>
        {!budget && idleBudget.loading && <p role="status" className="muted">Loading meters…</p>}
        {!budget && idleBudget.error && <ErrorBanner message={idleBudget.error.message} onRetry={idleBudget.reload} />}
        {budget && (
          <div className="meter-grid">
            <MeterCard label="Outbound requests" value={`${formatNumber(budget.total_outbound_requests)} of ${formatNumber(budget.max_requests)}`}>
              <BudgetBar total={budget.total_outbound_requests} softCap={budget.soft_cap} brake={budget.brake} max={budget.max_requests} />
            </MeterCard>
            <MeterCard
              label="LLM calls per minute"
              value={`${budget.llm_calls_last_minute} of ${budget.llm_rpm}`}
              ratio={budget.llm_calls_last_minute / budget.llm_rpm}
            />
            <MeterCard
              label="Estimated cost"
              value={`$${Number(budget.estimated_cost_usd).toFixed(2)} of $${budget.cost_limit_usd}`}
              ratio={budget.estimated_cost_usd / budget.cost_limit_usd}
            />
            <MeterCard
              label="Elapsed time"
              value={`${formatDuration(budget.elapsed_seconds)} of ${budget.max_elapsed_minutes} min`}
              ratio={budget.elapsed_seconds / (budget.max_elapsed_minutes * 60)}
              hint={
                budget.projected_minutes === null
                  ? undefined
                  : `Projected finish ${budget.projected_minutes} min. The kill switch trips above ${LIMITS.killSwitchMinutes}.`
              }
            />
          </div>
        )}
      </section>
    </>
  );
}

function ValidationSummary({ result }) {
  const { accepted, rejected, duplicates_removed } = result;
  return (
    <>
      <p>{`${accepted.length} accepted, ${rejected.length} rejected, ${duplicates_removed} duplicates removed`}</p>
      {rejected.length > 0 && (
        <ul>
          {rejected.slice(0, SHOWN_REJECTED).map((item) => (
            <li key={`${item.line}-${item.value}`}>
              Line {item.line}: <span className="mono">{item.value}</span> – {REASONS[item.reason] ?? item.reason}
            </li>
          ))}
          {rejected.length > SHOWN_REJECTED && <li>and {rejected.length - SHOWN_REJECTED} more</li>}
        </ul>
      )}
    </>
  );
}
