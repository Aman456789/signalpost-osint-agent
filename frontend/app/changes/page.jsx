"use client";

import { DataTable } from "@/components/DataTable";
import { listChanges } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { usePagedList } from "@/lib/hooks";

const show = (value) => (typeof value === "string" ? value : JSON.stringify(value ?? null));

const COLUMNS = [
  { key: "orgnr", header: "Company", render: (c) => <span className="mono">{c.orgnr}</span> },
  { key: "field", header: "Field", render: (c) => c.field },
  { key: "previous", header: "Previous value", render: (c) => <del><span className="visually-hidden">previous: </span>{show(c.previous_value)}</del> },
  { key: "new", header: "New value", render: (c) => <ins><span className="visually-hidden">new: </span>{show(c.new_value)}</ins> },
  { key: "time", header: "Change timestamp", render: (c) => formatDateTime(c.detected_at) },
];

export default function ChangesPage() {
  const list = usePagedList((cursor) => listChanges(cursor), []);
  return (
    <>
      <h1 className="page-title">Change Feed</h1>
      <DataTable
        columns={COLUMNS}
        rows={list.rows}
        rowKey={(c) => c.change_id}
        caption="Changes since the previous run"
        emptyTitle="No changes since the last run"
        emptyText="Change Radar re-checks only companies whose registry record changed."
        loading={list.loading}
        error={list.error}
        onRetry={list.reload}
        hasMore={list.hasMore}
        loadingMore={list.loadingMore}
        onLoadMore={list.loadMore}
      />
    </>
  );
}
