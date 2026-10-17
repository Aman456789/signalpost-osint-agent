"use client";

import { usePathname } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ApiError, eventsUrl, getBudget, getHealth, getJob, isFinished, useEventSource } from "@/lib/api";

const STORAGE_KEY = "signalpost.job";
const MAX_EVENTS = 2000;
const EMPTY = { jobId: null, job: null, budget: null, events: [] };

const JobContext = createContext(null);

export function useJob() {
  const value = useContext(JobContext);
  if (!value) throw new Error("useJob must be used inside JobProvider");
  return value;
}

export function JobProvider({ children }) {
  const pathname = usePathname();
  const pathJob = /^\/jobs\/([^/]+)/.exec(pathname)?.[1] ?? null;
  const [session, setSession] = useState(EMPTY);
  const [health, setHealth] = useState(null);
  const [reachable, setReachable] = useState(true);

  const trackJob = useCallback((id) => {
    try {
      sessionStorage.setItem(STORAGE_KEY, id);
    } catch {
      // storage can be blocked; the job is still tracked for this page view
    }
    setSession((s) => (s.jobId === id ? s : { jobId: id, job: null, budget: null, events: [] }));
  }, []);

  useEffect(() => {
    let saved = null;
    try {
      saved = sessionStorage.getItem(STORAGE_KEY);
    } catch {
      saved = null;
    }
    if (saved) trackJob(saved);
  }, [trackJob]);

  useEffect(() => {
    if (pathJob) trackJob(pathJob);
  }, [pathJob, trackJob]);

  useEffect(() => {
    let active = true;
    const check = () =>
      getHealth().then(
        (value) => { if (active) { setHealth(value); setReachable(true); } },
        () => { if (active) setReachable(false); },
      );
    void check();
    const timer = setInterval(check, 10_000);
    return () => { active = false; clearInterval(timer); };
  }, []);

  const jobId = session.jobId;
  const finished = session.job ? isFinished(session.job) : false;

  useEffect(() => {
    if (!jobId) return;
    let active = true;
    const refresh = async () => {
      try {
        const [job, budget] = await Promise.all([getJob(jobId), getBudget(jobId)]);
        if (active) setSession((s) => (s.jobId === jobId ? { ...s, job, budget } : s));
      } catch (err) {
        if (active && err instanceof ApiError && err.status === 404) setSession(EMPTY); // the API forgot this job
      }
    };
    void refresh();
    if (finished) return () => { active = false; };
    const timer = setInterval(refresh, 2000);
    return () => { active = false; clearInterval(timer); };
  }, [jobId, finished]);

  const handleEvent = useCallback((event) => {
    setSession((s) => (s.jobId === event.job_id ? { ...s, events: [...s.events, event].slice(-MAX_EVENTS) } : s));
  }, []);
  const stream = useEventSource(jobId ? eventsUrl(jobId) : null, handleEvent);

  const { events, budget } = session;
  const alerts = useMemo(() => ({
    softCap: Boolean(budget?.soft_cap_reached) || events.some((e) => e.type === "budget.soft_cap"),
    brake: Boolean(budget?.brake_tripped) || events.some((e) => e.type === "budget.brake"),
    killSwitch:
      Boolean(budget?.kill_switch_tripped) ||
      events.some((e) => e.type === "budget.kill_switch" || e.type === "killswitch.tripped"),
  }), [events, budget]);

  const connection = !jobId || finished ? (reachable ? "live" : "offline") : stream.state;

  return (
    <JobContext.Provider
      value={{ jobId, job: session.job, budget, health, events, connection, retryConnection: stream.retry, alerts, trackJob }}
    >
      {children}
    </JobContext.Provider>
  );
}
