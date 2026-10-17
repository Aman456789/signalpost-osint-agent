import { hostOf } from "@/lib/format";

const LABELS = {
  registry: "Registry",
  llm_verified: "Website, quote verified",
  structured_fallback: "Structured data",
};

export function SourceBadge({ method, url }) {
  const host = method === "registry" ? null : hostOf(url);
  return (
    <span className="badge tone-info">
      {LABELS[method] ?? method}
      {host && <span className="mono"> · {host}</span>}
    </span>
  );
}
