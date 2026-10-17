"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Banners } from "@/components/Banners";
import { ConnectionIndicator } from "@/components/ConnectionIndicator";
import { StatusBadge } from "@/components/StatusBadge";
import { humanize } from "@/lib/format";
import { useJob } from "@/lib/job-context";

export function AppShell({ children }) {
  const pathname = usePathname();
  const { jobId, job, health, connection, retryConnection, alerts } = useJob();

  const items = [
    { label: "Command Center", href: "/command-center" },
    { label: "Live Terminal", href: jobId ? `/jobs/${jobId}/terminal` : null },
    { label: "Dossier Explorer", href: "/dossiers" },
    { label: "Rejection Log", href: "/rejections" },
    { label: "Change Feed", href: "/changes" },
    { label: "Run Report", href: jobId ? `/jobs/${jobId}/report` : null },
  ];

  return (
    <div className="shell">
      <a className="skip-link" href="#content">Skip to content</a>
      <nav className="sidebar" aria-label="Main">
        <div className="brand">Signalpost</div>
        {items.map(({ label, href }) => {
          if (!href) {
            return (
              <span key={label} className="nav-item disabled" aria-disabled="true" title="Start a job first">
                {label}
              </span>
            );
          }
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link key={label} href={href} className="nav-item" aria-current={active ? "page" : undefined}>
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="main-col">
        <header className="topbar">
          <div className="row">
            <span className="label">Job</span>
            {job ? <StatusBadge status={job.status} /> : <span className="muted">No job</span>}
            {jobId && <span className="mono muted">{jobId.slice(0, 8)}</span>}
          </div>
          <div className="row">
            <span className="label">Mode</span>
            <span>{health ? humanize(health.mode) : "–"}{job ? ` · ${humanize(job.mode)}` : ""}</span>
            <ConnectionIndicator state={connection} onRetry={connection === "offline" && jobId ? retryConnection : undefined} />
          </div>
        </header>
        <Banners softCap={alerts.softCap} brake={alerts.brake} killSwitch={alerts.killSwitch} />
        <main id="content" className="content">{children}</main>
      </div>
    </div>
  );
}
