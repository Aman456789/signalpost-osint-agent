"use client";

import { useEffect, useRef } from "react";

export function SidePanel({ open, title, onClose, children }) {
  const closeButton = useRef(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    if (!open) return;
    closeButton.current?.focus();
    const onKey = (event) => {
      if (event.key === "Escape") onCloseRef.current();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (!open) return null;
  return (
    <aside className="side-panel" role="dialog" aria-label={title}>
      <div className="side-head">
        <h2>{title}</h2>
        <button ref={closeButton} type="button" className="btn small" onClick={onClose}>
          Close
        </button>
      </div>
      <div className="side-body">{children}</div>
    </aside>
  );
}
