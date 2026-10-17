import Link from "next/link";
import { EmptyState } from "@/components/EmptyState";
import { FlagChip } from "@/components/FlagChip";
import { SourceBadge } from "@/components/SourceBadge";
import { formatDate, humanize } from "@/lib/format";

export function FactList({ facts, orgnr }) {
  if (facts.length === 0) {
    return <EmptyState title="No published facts">Website facts appear here once a quote is verified.</EmptyState>;
  }
  return (
    <ul className="facts">
      {facts.map((fact) => (
        <li key={fact.fact_id} className="fact">
          <span className="fact-key">{humanize(fact.key)}</span>
          <p className="fact-value">{fact.value}</p>
          <p className="muted" lang="nb">{fact.value_no}</p>
          <div className="fact-meta">
            <span>Fact As-Of Date: {formatDate(fact.as_of)}</span>
            <SourceBadge method={fact.method} url={fact.source_url} />
            {Array.from(new Set([...fact.tags, ...fact.flags])).map((flag) => (
              <FlagChip key={flag} flag={flag} />
            ))}
            <Link href={`/dossiers/${orgnr}/facts/${fact.fact_id}`}>View evidence</Link>
          </div>
        </li>
      ))}
    </ul>
  );
}
