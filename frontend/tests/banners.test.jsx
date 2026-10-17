import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Banners } from "@/components/Banners";

describe("Banners", () => {
  it("shows nothing when no limit is hit", () => {
    render(<Banners softCap={false} brake={false} killSwitch={false} />);
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("uses role status for the soft cap warning", () => {
    render(<Banners softCap brake={false} killSwitch={false} />);
    expect(screen.getByRole("status")).toHaveTextContent("Soft cap reached");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("uses role alert for the brake and the kill switch", () => {
    render(<Banners softCap={false} brake killSwitch />);
    const alerts = screen.getAllByRole("alert");
    expect(alerts).toHaveLength(2);
    expect(alerts[0]).toHaveTextContent("Request brake tripped");
    expect(alerts[1]).toHaveTextContent("Time limit safeguard active");
    expect(screen.queryByRole("status")).toBeNull();
  });
});
