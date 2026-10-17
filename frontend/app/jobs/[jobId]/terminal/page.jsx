"use client";

import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { EmptyState } from "@/components/EmptyState";
import { ErrorBanner } from "@/components/ErrorBanner";
import { formatTime } from "@/lib/format";
import { useJob } from "@/lib/job-context";

const GROUPS = {
  all: "All events",
  company: "Companies",
  budget: "Budget and time",
  job: "Job",
  error: "Errors",
};

function groupOf(type) {
  if (type.startsWith("company.")) return "company";
  if (type.startsWith("budget.") || type.startsWith("time.") || type === "killswitch.tripped") return "budget";
  if (type === "error" || type === "job.storage_failed") return "error";
  return "job";
}

export default function TerminalPage() {
  const { jobId } = useParams();
  const { events, connection, retryConnection } = useJob();
  const [group, setGroup] = useState("all");
  const [text, setText] = useState("");
  const [follow, setFollow] = useState(true);
  const box = useRef(null);

  const needle = text.trim().toLowerCase();
  const visible = events.filter((event) => {
    if (event.job_id !== jobId) return false;
    if (group !== "all" && groupOf(event.type) !== group) return false;
    return !needle || `${event.type} ${event.orgnr ?? ""} ${event.message}`.toLowerCase().includes(needle);
  });

  useEffect(() => {
    if (follow && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [visible.length, follow]);

  function onScroll() {
    const el = box.current;
    if (el && follow && el.scrollHeight - el.scrollTop - el.clientHeight > 40) setFollow(false);
  }

  return (
    <>
      <h1 className="page-title">Live Terminal</h1>
      <p className="muted">Job <span className="mono">{jobId}</span></p>

      {connection === "offline" && (
        <ErrorBanner message="The event stream is disconnected." onRetry={retryConnection} />
      )}

      <div className="toolbar">
        <label htmlFor="group" className="label">Show</label>
        <select id="group" className="input" value={group} onChange={(e) => setGroup(e.target.value)}>
          {Object.entries(GROUPS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <label htmlFor="event-filter" className="label">Filter</label>
        <input
          id="event-filter"
          type="search"
          className="input"
          placeholder="Event type, organisation number or text"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <label className="row" style={{ gap: 6 }}>
          <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} />
          Follow
        </label>
      </div>

      {visible.length === 0 ? (
        <EmptyState title="No events yet">Events appear here as the job runs.</EmptyState>
      ) : (
        <div ref={box} className="terminal" onScroll={onScroll} role="log" aria-label="Job events" tabIndex={0}>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {visible.map((event) => (
              <li key={event.id} className={`term-line ${groupOf(event.type) === "error" ? "danger" : ""}`}>
                <time className="term-time" dateTime={event.ts}>{formatTime(event.ts)}</time>
                <span className="term-type">{event.type}</span>
                {event.orgnr && <span>{event.orgnr}</span>}
                <span>{event.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}
