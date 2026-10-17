import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EvidenceViewer } from "@/components/EvidenceViewer";

const quote = "We build electric boats";
const text = `Home. ${quote} for the Nordic market.`;
const start = text.indexOf(quote);
const hash = "a".repeat(64);

const evidence = {
  fact: {
    fact_id: "f1", orgnr: "923609016", key: "products", value: "Electric boats", value_no: "Elektriske båter",
    quote, registry_json_path: null, method: "llm_verified", source_id: "s1", source_url: "https://example.no/about",
    retrieved_at: "2026-10-17T09:00:00Z", sha256: hash, as_of: "2026-10-17T00:00:00Z", tags: [], flags: ["self_reported"],
    identity_score: "0.90", q: "1.00", v: "1.00", g: "1.00", s: "1.00", f: "1.00", confidence: "0.95",
    publication_status: "published", validation_id: "v1", created_at: "2026-10-17T09:01:00Z",
  },
  quote,
  snapshot: { sha256: hash, text, highlight: { start, end: start + quote.length }, offset_unit: "unicode_code_points" },
  source: null,
  source_url: "https://example.no/about",
  final_url: null,
  retrieved_at: "2026-10-17T09:00:00Z",
  sha256: hash,
  validation: { validation_id: "v1", publication_status: "published" },
  confidence: { confidence: "0.95", identity_score: "0.90", q: "1.00", v: "1.00", g: "1.00", s: "1.00", f: "1.00" },
};

describe("EvidenceViewer", () => {
  it("highlights the quote in the saved page text", () => {
    const { container } = render(<EvidenceViewer evidence={evidence} />);
    expect(container.querySelector("mark")?.textContent).toBe(quote);
  });

  it("shows both dates, the hash and a copy button", () => {
    render(<EvidenceViewer evidence={evidence} />);
    expect(screen.getByText("Fact As-Of Date")).toBeInTheDocument();
    expect(screen.getByText("Retrieval Date")).toBeInTheDocument();
    expect(screen.getByText(hash)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy SHA-256" })).toBeInTheDocument();
  });

  it("explains a registry fact that has no page text", () => {
    const registry = {
      ...evidence, quote: null, snapshot: null,
      fact: { ...evidence.fact, method: "registry", quote: null, registry_json_path: "$.naeringskode1.beskrivelse" },
    };
    const { container } = render(<EvidenceViewer evidence={registry} />);
    expect(container.querySelector("mark")).toBeNull();
    expect(screen.getByText("$.naeringskode1.beskrivelse")).toBeInTheDocument();
  });
});
