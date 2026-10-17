import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OutcomesTable } from "@/components/OutcomesTable";

describe("OutcomesTable", () => {
  it("shows no_website only as a sub-line under registry_only", () => {
    render(<OutcomesTable outcomes={{ published: 3, registry_only: 5, failed: 1 }} total={9} noWebsite={2} />);

    const bodyRows = screen.getAllByRole("row").slice(1); // skip the header row
    expect(bodyRows).toHaveLength(3);
    expect(bodyRows.some((row) => row.textContent?.startsWith("no_website"))).toBe(false);
    expect(screen.getAllByText(/no_website/)).toHaveLength(1);

    const registryOnly = bodyRows.find((row) => row.textContent?.includes("Registry only"));
    expect(registryOnly).toBeDefined();
    expect(within(registryOnly).getByText("of which flagged no_website: 2")).toBeInTheDocument();
  });

  it("keeps the registry_only row and its sub-line when the count is zero", () => {
    render(<OutcomesTable outcomes={{ published: 2 }} total={2} noWebsite={0} />);
    expect(screen.getByText("of which flagged no_website: 0")).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(3);
  });
});
