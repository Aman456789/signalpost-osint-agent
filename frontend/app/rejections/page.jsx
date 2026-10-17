"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { DataTable } from "@/components/DataTable";
import { REJECTION_REASONS, VALIDATION_STAGES, listRejections } from "@/lib/api";
import { formatDateTime, humanize } from "@/lib/format";
import { usePagedList } from "@/lib/hooks";

const COLUMNS = [
  { key: "time", header: "Rejected at", render: (r) => formatDateTime(r.rejected_at) },
  { key: "orgnr", header: "Organisation number", render: (r) => <span className="mono">{r.orgnr}</span> },
  { key: "stage", header: "Stage", render: (r) => humanize(r.validation_stage) },
  { key: "reason", header: "Reason code", render: (r) => <span className="mono">{r.reason_code}</span> },
  { key: "value", header: "Rejected value", render: (r) => (r.rejected_value ? r.rejected_value.slice(0, 80) : "–") },
  {
    key: "diagnostic",
    header: "Diagnostic",
    render: (r) =>
      Object.keys(r.diagnostic).length === 0 ? (
        "–"
      ) : (
        <details>
          <summary>Show</summary>
          <pre className="diag">{JSON.stringify(r.diagnostic, null, 2)}</pre>
        </details>
      ),
  },
];

export default function RejectionsPage() {
  return (
    <Suspense fallback={<p role="status" className="muted">Loading…</p>}>
      <RejectionLog />
    </Suspense>
  );
}

function RejectionLog() {
  const params = useSearchParams();
  const jobId = params.get("job_id") ?? "";
  const [reason, setReason] = useState(params.get("reason") ?? "");
  const [stage, setStage] = useState("");

  const list = usePagedList(
    (cursor) => listRejections({ job_id: jobId, reason, stage, cursor }),
    [jobId, reason, stage],
  );

  return (
    <>
      <h1 className="page-title">Rejection Log</h1>
      <p className="muted">
        Candidate facts that failed a check, with the first stage that rejected them.{jobId ? " Showing one job only." : ""}
      </p>
      <DataTable
        columns={COLUMNS}
        rows={list.rows}
        rowKey={(r) => r.rejection_id}
        caption="Rejected candidate facts"
        emptyTitle="No rejections"
        emptyText="Nothing has been rejected for this selection."
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        toolbar={
          <>
            <label htmlFor="reason-filter" className="label">Reason</label>
            <select id="reason-filter" className="input" value={reason} onChange={(e) => setReason(e.target.value)}>
              <option value="">All reasons</option>
              {REJECTION_REASONS.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
            </select>
            <label htmlFor="stage-filter" className="label">Stage</label>
            <select id="stage-filter" className="input" value={stage} onChange={(e) => setStage(e.target.value)}>
              <option value="">All stages</option>
              {VALIDATION_STAGES.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}
            </select>
          </>
        }
        hasMore={list.hasMore}
        loadingMore={list.loadingMore}
        onLoadMore={list.loadMore}
      />
    </>
  );
}
