import { humanize } from "@/lib/format";

const TONES = {
  published: "ok", completed: "ok", active: "ok", verified: "ok",
  registry_only: "info", pass1_running: "info", pass2_running: "info", pass1_complete: "info",
  stopped_budget: "warn", stopped_time: "warn", abstained: "warn",
  failed: "danger", registry_unavailable: "danger", stopped_storage: "danger",
  bankrupt: "danger", deleted: "danger", dissolved: "danger",
};

const LABELS = {
  pass1_running: "Pass 1 running",
  pass1_complete: "Pass 1 complete",
  pass2_running: "Pass 2 running",
};

export function StatusBadge({ status }) {
  const tone = TONES[status] ?? "neutral";
  return <span className={`badge tone-${tone}`}>{LABELS[status] ?? humanize(status)}</span>;
}
