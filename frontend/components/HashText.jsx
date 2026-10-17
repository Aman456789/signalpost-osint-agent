"use client";

import { useState } from "react";

export function HashText({ value, label = "SHA-256" }) {
  const [state, setState] = useState("idle");

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setState("copied");
    } catch {
      setState("failed");
    }
    setTimeout(() => setState("idle"), 1500);
  }

  return (
    <span className="hash">
      <code className="mono">{value}</code>
      <button type="button" className="btn small" onClick={copy} aria-label={`Copy ${label}`}>
        {state === "copied" ? "Copied" : state === "failed" ? "Copy failed" : "Copy"}
      </button>
    </span>
  );
}
