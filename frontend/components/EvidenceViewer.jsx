import { FlagChip } from "@/components/FlagChip";
import { HashText } from "@/components/HashText";
import { HighlightedText } from "@/components/HighlightedText";
import { SourceBadge } from "@/components/SourceBadge";
import { formatDate, formatDateTime, humanize, safeHref, score } from "@/lib/format";

export function EvidenceViewer({ evidence }) {
  const { fact, snapshot, confidence } = evidence;
  const href = safeHref(evidence.final_url ?? evidence.source_url);
  const flags = Array.from(new Set([...fact.tags, ...fact.flags]));

  return (
    <div className="evidence">
      <section className="panel stack" aria-labelledby="fact-heading">
        <h2 id="fact-heading">Fact</h2>
        <span className="fact-key">{humanize(fact.key)}</span>
        <p className="fact-value">{fact.value}</p>
        <p className="muted" lang="nb">{fact.value_no}</p>
        {evidence.quote && <blockquote className="quote">{evidence.quote}</blockquote>}
        <dl className="dl">
          <dt>Fact As-Of Date</dt>
          <dd>{formatDate(fact.as_of)}</dd>
          <dt>Retrieval Date</dt>
          <dd>{formatDateTime(evidence.retrieved_at)}</dd>
          <dt>Source</dt>
          <dd>
            <SourceBadge method={fact.method} url={evidence.source_url} />
            {href && (
              <>
                {" "}
                <a href={href} target="_blank" rel="noreferrer noopener">Open page</a>
              </>
            )}
          </dd>
          <dt>SHA-256</dt>
          <dd><HashText value={evidence.sha256} /></dd>
          <dt>Confidence</dt>
          <dd>
            {score(confidence.confidence)} (identity {score(confidence.identity_score)}, Q {score(confidence.q)}, V {score(confidence.v)},
            G {score(confidence.g)}, S {score(confidence.s)}, F {score(confidence.f)})
          </dd>
          <dt>Status</dt>
          <dd>{humanize(evidence.validation.publication_status)}</dd>
        </dl>
        {flags.length > 0 && (
          <div className="chips">
            {flags.map((flag) => <FlagChip key={flag} flag={flag} />)}
          </div>
        )}
      </section>

      <section className="panel stack" aria-labelledby="page-heading">
        <h2 id="page-heading">Saved page text</h2>
        {snapshot ? (
          <>
            {snapshot.highlight === null && <p role="status" className="muted">The quote was not found in the saved text.</p>}
            <HighlightedText text={snapshot.text} start={snapshot.highlight?.start ?? null} end={snapshot.highlight?.end ?? null} />
          </>
        ) : (
          <p className="muted">
            This fact comes from the registry (<span className="mono">{fact.registry_json_path}</span>). There is no saved page text.
          </p>
        )}
      </section>
    </div>
  );
}
