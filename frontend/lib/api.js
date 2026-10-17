"use client";

import { useEffect, useRef, useState } from "react";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
export const LIMITS = { maxRequests: 2000, softCap: 1700, brake: 1950, killSwitchMinutes: 38 };

export const PROCESSING_STATUSES = [
  "pending", "pass1_running", "pass1_complete", "pass2_running", "published", "registry_only",
  "not_found", "registry_unavailable", "not_processed_budget", "failed",
];
export const REJECTION_REASONS = [
  "schema_invalid", "identity_failed", "quote_not_found", "quote_translated", "value_unsupported",
  "digit_unsupported", "name_unsupported", "money_blocked", "below_threshold", "llm_invalid_json",
  "fetch_failed", "conflicts_with_registry",
];
export const VALIDATION_STAGES = ["fetch", "schema", "identity", "quote", "value", "money", "registry_clash", "confidence"];

export class ApiError extends Error {
  constructor(status, message, body) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export function errorMessage(err) {
  return err instanceof ApiError ? err.message : "Something went wrong. Try again.";
}

async function toApiError(res) {
  let body = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  return new ApiError(res.status, body?.detail ?? body?.title ?? `Request failed with status ${res.status}`, body);
}

async function request(path, init) {
  let res;
  try {
    res = await fetch(`${API_BASE}/api${path}`, init);
  } catch {
    throw new ApiError(0, "Cannot reach the agent service. Check that make api is still running.");
  }
  if (!res.ok) throw await toApiError(res);
  return res.json();
}

function post(body, headers = {}) {
  return { method: "POST", headers: { "Content-Type": "application/json", ...headers }, body: JSON.stringify(body) };
}

function query(params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

// E1. A 422 means nothing valid was found; its body still lists the rejected lines.
export async function validateInputs(text) {
  try {
    return await request("/inputs/validate", post({ text }));
  } catch (err) {
    const rejected = err instanceof ApiError ? err.body?.rejected : null;
    if (err instanceof ApiError && err.status === 422 && rejected) {
      return { accepted: [], rejected, duplicates_removed: 0 };
    }
    throw err;
  }
}

// E2
export function startJob(orgnrs) {
  return request("/jobs", post({ orgnrs, mode: "daily_test" }, { "Idempotency-Key": crypto.randomUUID() }));
}

// E3
export const getJob = (jobId) => request(`/jobs/${jobId}`);

// E4 (see useEventSource)
export const eventsUrl = (jobId) => `${API_BASE}/api/jobs/${jobId}/events`;

// E5
export const listDossiers = (params) => request(`/dossiers${query({ limit: 50, ...params })}`);

// E6
export const getDossier = (orgnr) => request(`/dossiers/${encodeURIComponent(orgnr)}`);

// E7
export const getEvidence = (orgnr, factId) =>
  request(`/dossiers/${encodeURIComponent(orgnr)}/facts/${encodeURIComponent(factId)}/evidence`);

// E8
export const listRejections = (params) => request(`/rejections${query({ limit: 50, ...params })}`);

// E9
export const listChanges = (cursor) => request(`/changes${query({ limit: 50, cursor })}`);

// E10
export const getReport = (jobId) => request(`/jobs/${jobId}/report`);

// E11
export const getBudget = (jobId) => request(`/budget${query({ job_id: jobId })}`);

// E12. A 503 still carries the health body, so return it instead of throwing.
export async function getHealth() {
  try {
    return await request("/health");
  } catch (err) {
    if (err instanceof ApiError && err.status === 503 && err.body && typeof err.body === "object" && "dependencies" in err.body) {
      return err.body;
    }
    throw err;
  }
}

const FINISHED = ["completed", "stopped_budget", "stopped_time", "stopped_storage", "failed", "cancelled"];

export function isFinished(job) {
  return job.ended_at !== null || FINISHED.includes(job.status);
}

const MAX_FAILURES = 5;

function sleep(ms, signal) {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => { clearTimeout(timer); resolve(); }, { once: true });
  });
}

function parseFrame(frame) {
  const data = frame
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (!data) return null; // heartbeat comment
  try {
    return JSON.parse(data);
  } catch {
    return null;
  }
}

async function readStream(url, cursor, signal, emit, onOpen) {
  const headers = { Accept: "text/event-stream" };
  if (cursor.id > 0) headers["Last-Event-ID"] = String(cursor.id);
  const res = await fetch(url, { headers, signal });
  if (!res.ok || !res.body) throw new ApiError(res.status, `Event stream failed with status ${res.status}`);
  onOpen();

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let ended = false;
  let received = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) return { ended, received };
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const event = parseFrame(frame);
      if (!event || event.id <= cursor.id) continue;
      cursor.id = event.id;
      received += 1;
      emit(event);
      if (event.type === "job.finished" || event.type === "error") ended = true;
    }
  }
}

async function follow(url, cursor, signal, emit, setState) {
  let failures = 0;
  let quiet = 0;
  while (!signal.aborted) {
    try {
      const { ended, received } = await readStream(url, cursor, signal, emit, () => {
        failures = 0;
        setState("live");
      });
      if (ended) return;
      quiet = received > 0 ? 0 : quiet + 1;
      if (quiet >= 3) { setState("offline"); return; }
    } catch (err) {
      if (signal.aborted) return;
      if (err instanceof ApiError && err.status >= 400 && err.status < 500) { setState("offline"); return; }
      failures += 1;
      if (failures >= MAX_FAILURES) { setState("offline"); return; }
    }
    setState("reconnecting");
    await sleep(Math.min(500 * 2 ** failures, 8000), signal);
  }
}

// fetch() instead of EventSource, because EventSource cannot set the Last-Event-ID header itself.
export function useEventSource(url, onEvent) {
  const [state, setState] = useState("reconnecting");
  const [attempt, setAttempt] = useState(0);
  const handler = useRef(onEvent);
  const cursor = useRef({ url: "", id: 0 });

  useEffect(() => {
    handler.current = onEvent;
  });

  useEffect(() => {
    if (!url) {
      setState("offline");
      return;
    }
    if (cursor.current.url !== url) cursor.current = { url, id: 0 };
    const controller = new AbortController();
    setState("reconnecting");
    void follow(url, cursor.current, controller.signal, (event) => handler.current(event), setState);
    return () => controller.abort();
  }, [url, attempt]);

  return { state, retry: () => setAttempt((n) => n + 1) };
}
