import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BudgetBar } from "@/components/BudgetBar";

describe("BudgetBar", () => {
  it("places the soft cap and brake markers on a 2,000 scale", () => {
    const { container } = render(<BudgetBar total={1000} />);
    const bar = screen.getByRole("progressbar", { name: "Outbound requests" });
    expect(bar).toHaveAttribute("aria-valuemax", "2000");
    expect(bar).toHaveAttribute("aria-valuenow", "1000");
    expect(container.querySelector('[data-marker="soft"]')).toHaveStyle({ left: "85%" });
    expect(container.querySelector('[data-marker="brake"]')).toHaveStyle({ left: "97.5%" });
    expect(screen.getByText("Soft cap 1,700")).toBeInTheDocument();
    expect(screen.getByText("Brake 1,950")).toBeInTheDocument();
    expect(screen.getByText("Maximum 2,000")).toBeInTheDocument();
  });

  it("changes colour class at the soft cap and at the brake", () => {
    const fill = (total) => render(<BudgetBar total={total} />).container.querySelector(".budget-fill");
    expect(fill(1699)).toHaveClass("ok");
    expect(fill(1700)).toHaveClass("warn");
    expect(fill(1950)).toHaveClass("danger");
  });
});
