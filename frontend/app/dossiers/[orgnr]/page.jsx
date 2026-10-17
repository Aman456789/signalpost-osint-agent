"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Fragment } from "react";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBanner } from "@/components/ErrorBanner";
import { FactList } from "@/components/FactList";
import { FlagChip } from "@/components/FlagChip";
import { StatusBadge } from "@/components/StatusBadge";
import { getDossier } from "@/lib/api";
import { formatDateTime, formatMoney, humanize, safeHref } from "@/lib/format";
import { useLoad } from "@/lib/hooks";

export default function DossierPage() {
  const { orgnr } = useParams();
  const { data, error, loading, reload } = useLoad(() => getDossier(orgnr), [orgnr]);

  if (loading) return <p role="status" className="muted">Loading…</p>;
  if (error?.status === 404) {
    return (
      <EmptyState title="Dossier not found" action={<Link href="/dossiers">Back to the Dossier Explorer</Link>}>
        {`There is no dossier for ${orgnr} yet.`}
      </EmptyState>
    );
  }
  if (error || !data) return <ErrorBanner message={error?.message ?? "The dossier could not be loaded."} onRetry={reload} />;

  const website = safeHref(data.website_url);
  return (
    <>
      <nav aria-label="Breadcrumb"><Link href="/dossiers">Dossiers</Link> / {data.orgnr}</nav>
      <h1 className="page-title">{data.legal_name ?? "Unnamed company"}</h1>

      <section className="panel stack" aria-labelledby="summary-heading">
        <h2 id="summary-heading">Summary</h2>
        <dl className="dl">
          <dt>Organisation number</dt><dd className="mono">{data.orgnr}</dd>
          <dt>Organisation form</dt><dd>{data.org_form ?? "–"}</dd>
          <dt>Registry status</dt><dd><StatusBadge status={data.registry_status} /></dd>
          <dt>Processing status</dt><dd><StatusBadge status={data.processing_status} /></dd>
          <dt>Retrieval Date</dt><dd>{formatDateTime(data.data_freshness)}</dd>
          <dt>Website</dt>
          <dd>{website ? <a href={website} target="_blank" rel="noreferrer noopener">{data.website_url}</a> : "No website in the registry"}</dd>
          <dt>Verified facts</dt><dd>{data.verified_fact_count}</dd>
        </dl>
        {data.flags.length > 0 && <div className="chips">{data.flags.map((flag) => <FlagChip key={flag} flag={flag} />)}</div>}
      </section>

      <section className="panel stack" aria-labelledby="facts-heading">
        <h2 id="facts-heading">Published facts</h2>
        <FactList facts={data.facts} orgnr={data.orgnr} />
      </section>

      <section className="panel stack" aria-labelledby="fin-heading">
        <h2 id="fin-heading">Financial summary</h2>
        {data.financial_summary.length === 0 ? (
          <EmptyState title="Financials unavailable">No annual accounts were found in the registry.</EmptyState>
        ) : (
          <div className="table-wrap">
            <table className="data">
              <caption className="visually-hidden">Financial summary</caption>
              <thead>
                <tr>
                  <th scope="col">Metric</th>
                  <th scope="col">Fiscal year</th>
                  <th scope="col" className="right">Amount</th>
                  <th scope="col">Method</th>
                  <th scope="col">Status</th>
                  <th scope="col">Retrieval Date</th>
                </tr>
              </thead>
              <tbody>
                {data.financial_summary.map((row) => (
                  <tr key={row.financial_id}>
                    <td>{humanize(row.metric)}</td>
                    <td>{row.fiscal_year}</td>
                    <td className="right">
                      {row.amount_base !== null ? formatMoney(row.amount_base, row.currency ?? "") : row.unavailable_reason ?? "Unavailable"}
                    </td>
                    <td>{humanize(row.method)}</td>
                    <td><StatusBadge status={row.verification_status} /></td>
                    <td>{formatDateTime(row.retrieved_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {data.roles.length > 0 && (
        <section className="panel stack" aria-labelledby="roles-heading">
          <h2 id="roles-heading">Roles</h2>
          <dl className="dl">
            {data.roles.map((role, index) => (
              <Fragment key={`${role.name}-${index}`}>
                <dt>{humanize(role.role)}</dt>
                <dd>{role.name}</dd>
              </Fragment>
            ))}
          </dl>
        </section>
      )}

      {data.registry_fields && (
        <section className="panel stack" aria-labelledby="registry-heading">
          <h2 id="registry-heading">Registry fields</h2>
          <dl className="dl">
            {Object.entries(data.registry_fields).map(([key, value]) => (
              <Fragment key={key}>
                <dt>{humanize(key)}</dt>
                <dd>{value !== null && typeof value === "object" ? JSON.stringify(value) : String(value ?? "–")}</dd>
              </Fragment>
            ))}
          </dl>
        </section>
      )}
    </>
  );
}
