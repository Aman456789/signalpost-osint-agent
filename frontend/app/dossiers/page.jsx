"use client";

import Link from "next/link";
import { useState } from "react";
import { DataTable } from "@/components/DataTable";
import { ErrorBanner } from "@/components/ErrorBanner";
import { FactList } from "@/components/FactList";
import { FlagChip } from "@/components/FlagChip";
import { SidePanel } from "@/components/SidePanel";
import { StatusBadge } from "@/components/StatusBadge";
import { PROCESSING_STATUSES, getDossier, listDossiers } from "@/lib/api";
import { formatDateTime, humanize } from "@/lib/format";
import { useDebounced, useLoad, usePagedList } from "@/lib/hooks";

const COLUMNS = [
  { key: "orgnr", header: "Organisation number", sortKey: "orgnr", render: (d) => <span className="mono">{d.orgnr}</span> },
  { key: "name", header: "Legal name", sortKey: "name", render: (d) => d.legal_name ?? "–" },
  { key: "registry", header: "Registry status", render: (d) => <StatusBadge status={d.registry_status} /> },
  { key: "processing", header: "Processing status", render: (d) => <StatusBadge status={d.processing_status} /> },
  { key: "retrieval", header: "Retrieval Date", render: (d) => formatDateTime(d.data_freshness) },
  { key: "financials", header: "Financials", render: (d) => (d.financials_available ? "Available" : "Unavailable") },
  { key: "facts", header: "Verified facts", sortKey: "facts", align: "right", render: (d) => d.verified_fact_count },
];

export default function DossiersPage() {
  const [search, setSearch] = useState("");
  const q = useDebounced(search, 300);
  const [status, setStatus] = useState("");
  const [sort, setSort] = useState({ key: "updated_at", order: "desc" });
  const [selected, setSelected] = useState(null);

  const list = usePagedList(
    (cursor) => listDossiers({ q, status, sort: sort.key, order: sort.order, cursor }),
    [q, status, sort.key, sort.order],
  );

  function changeSort(key) {
    setSort((s) => (s.key === key ? { key, order: s.order === "asc" ? "desc" : "asc" } : { key, order: key === "facts" ? "desc" : "asc" }));
  }

  return (
    <>
      <h1 className="page-title">Dossier Explorer</h1>
      <DataTable
        columns={COLUMNS}
        rows={list.rows}
        rowKey={(d) => d.orgnr}
        caption="Company dossiers"
        emptyTitle="No dossiers found"
        emptyText="Start a job in the Command Center, or change the search and status filter."
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        sort={sort}
        onSortChange={changeSort}
        filter={{ label: "Search", placeholder: "Organisation number or name", value: search, onChange: setSearch }}
        toolbar={
          <>
            <label htmlFor="status-filter" className="label">Processing status</label>
            <select id="status-filter" className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All statuses</option>
              {PROCESSING_STATUSES.map((value) => (
                <option key={value} value={value}>{humanize(value)}</option>
              ))}
            </select>
          </>
        }
        hasMore={list.hasMore}
        loadingMore={list.loadingMore}
        onLoadMore={list.loadMore}
        onRowClick={(d) => setSelected(d.orgnr)}
      />

      <SidePanel open={selected !== null} title={`Dossier ${selected ?? ""}`} onClose={() => setSelected(null)}>
        {selected && <DossierPanelBody orgnr={selected} />}
      </SidePanel>
    </>
  );
}

function DossierPanelBody({ orgnr }) {
  const { data, error, loading, reload } = useLoad(() => getDossier(orgnr), [orgnr]);
  if (loading) return <p role="status" className="muted">Loading…</p>;
  if (error || !data) return <ErrorBanner message={error?.message ?? "The dossier could not be loaded."} onRetry={reload} />;
  return (
    <>
      <div className="stack">
        <h3>{data.legal_name ?? "Unnamed company"}</h3>
        <div className="chips">
          <StatusBadge status={data.registry_status} />
          <StatusBadge status={data.processing_status} />
          {data.flags.map((flag) => <FlagChip key={flag} flag={flag} />)}
        </div>
        <p className="muted">Retrieval Date: {formatDateTime(data.data_freshness)}</p>
        <Link href={`/dossiers/${orgnr}`}>Open full dossier</Link>
      </div>
      <FactList facts={data.facts} orgnr={orgnr} />
    </>
  );
}
