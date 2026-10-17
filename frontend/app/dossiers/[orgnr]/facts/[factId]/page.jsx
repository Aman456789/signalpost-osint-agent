"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBanner } from "@/components/ErrorBanner";
import { EvidenceViewer } from "@/components/EvidenceViewer";
import { getEvidence } from "@/lib/api";
import { useLoad } from "@/lib/hooks";

export default function EvidencePage() {
  const { orgnr, factId } = useParams();
  const { data, error, loading, reload } = useLoad(() => getEvidence(orgnr, factId), [orgnr, factId]);

  return (
    <>
      <nav aria-label="Breadcrumb">
        <Link href="/dossiers">Dossiers</Link> / <Link href={`/dossiers/${orgnr}`}>{orgnr}</Link> / Evidence
      </nav>
      <h1 className="page-title">Evidence Viewer</h1>
      {loading && <p role="status" className="muted">Loading…</p>}
      {error?.status === 404 && <EmptyState title="Evidence not found">{error.message}</EmptyState>}
      {error && error.status !== 404 && <ErrorBanner message={error.message} onRetry={reload} />}
      {data && <EvidenceViewer evidence={data} />}
    </>
  );
}
