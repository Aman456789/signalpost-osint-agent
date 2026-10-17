import { humanize } from "@/lib/format";

export function FlagChip({ flag }) {
  const tone = flag === "no_website" || flag === "financials_unavailable" ? "neutral" : "warn";
  return (
    <span className={`badge tone-${tone}`} title={flag}>
      {humanize(flag)}
    </span>
  );
}
