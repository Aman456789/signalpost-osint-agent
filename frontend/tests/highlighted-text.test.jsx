import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HighlightedText } from "@/components/HighlightedText";

describe("HighlightedText", () => {
  it("marks the range given in code points, even after an emoji", () => {
    const text = "😀 We build boats in Bergen.";
    const quote = "boats in Bergen";
    // indexOf counts UTF-16 units; the API counts code points
    const start = Array.from(text.slice(0, text.indexOf(quote))).length;
    const { container } = render(<HighlightedText text={text} start={start} end={start + quote.length} />);
    expect(container.querySelector("mark")?.textContent).toBe(quote);
    expect(container.textContent).toBe(text);
  });

  it("shows plain text when there is no range", () => {
    const { container } = render(<HighlightedText text="Nothing marked" start={null} end={null} />);
    expect(container.querySelector("mark")).toBeNull();
    expect(container.textContent).toBe("Nothing marked");
  });
});
