import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CommandCenterPage from "@/app/command-center/page";
import { getBudget, startJob, validateInputs } from "@/lib/api";

const mocks = vi.hoisted(() => ({ trackJob: vi.fn() }));

vi.mock("next/link", async () => {
  const { createElement } = await import("react");
  return { default: ({ href, children }) => createElement("a", { href }, children) };
});

vi.mock("@/lib/api", async (importOriginal) => {
  const real = await importOriginal();
  return { ...real, validateInputs: vi.fn(), startJob: vi.fn(), getBudget: vi.fn() };
});

vi.mock("@/lib/job-context", () => ({
  useJob: () => ({
    jobId: null, job: null, budget: null, health: null, events: [], connection: "live",
    retryConnection: vi.fn(), alerts: { softCap: false, brake: false, killSwitch: false }, trackJob: mocks.trackJob,
  }),
}));

describe("Command Center", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getBudget).mockReturnValue(new Promise(() => {}));
  });

  it("validates the input, then starts a job", async () => {
    vi.mocked(validateInputs).mockResolvedValue({ accepted: ["923609016"], rejected: [], duplicates_removed: 0 });
    vi.mocked(startJob).mockResolvedValue({
      job_id: "job-1", status: "queued", accepted_count: 1, rejected: [], duplicates_removed: 0,
      limits: { max_requests: 2000, soft_cap: 1700, brake: 1950, max_cost_usd: 10, max_elapsed_minutes: 45 },
      events_url: "/api/jobs/job-1/events",
    });
    render(<CommandCenterPage />);

    const field = screen.getByLabelText("Organisation numbers");
    fireEvent.change(field, { target: { value: "923609016" } });
    fireEvent.blur(field);
    expect(await screen.findByText("1 accepted, 0 rejected, 0 duplicates removed")).toBeInTheDocument();
    expect(validateInputs).toHaveBeenCalledWith("923609016");

    fireEvent.click(screen.getByRole("button", { name: "Start job" }));
    expect(await screen.findByRole("heading", { name: "Job started" })).toBeInTheDocument();
    expect(startJob).toHaveBeenCalledWith(["923609016"]);
    expect(mocks.trackJob).toHaveBeenCalledWith("job-1");
    expect(screen.getByRole("link", { name: "Open Live Terminal" })).toHaveAttribute("href", "/jobs/job-1/terminal");
  });

  it("keeps Start disabled when nothing is valid", async () => {
    vi.mocked(validateInputs).mockResolvedValue({
      accepted: [], rejected: [{ line: 1, value: "123", reason: "length_not_9" }], duplicates_removed: 0,
    });
    render(<CommandCenterPage />);

    const field = screen.getByLabelText("Organisation numbers");
    fireEvent.change(field, { target: { value: "123" } });
    fireEvent.blur(field);
    expect(await screen.findByText("Not 9 digits", { exact: false })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start job" })).toBeDisabled();
  });
});
