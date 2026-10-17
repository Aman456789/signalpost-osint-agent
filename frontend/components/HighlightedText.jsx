"use client";

import { useEffect, useRef } from "react";

// start and end are Unicode code points, as the API sends them
export function HighlightedText({ text, start, end }) {
  const mark = useRef(null);

  useEffect(() => {
    mark.current?.scrollIntoView?.({ block: "center" });
  }, [text, start, end]);

  // Python counts code points and JavaScript strings count UTF-16 units, so split by code point.
  const points = Array.from(text);
  if (start === null || end === null || start < 0 || end <= start || end > points.length) {
    return <pre className="page-text">{text}</pre>;
  }
  return (
    <pre className="page-text">
      {points.slice(0, start).join("")}
      <mark ref={mark}>{points.slice(start, end).join("")}</mark>
      {points.slice(end).join("")}
    </pre>
  );
}
