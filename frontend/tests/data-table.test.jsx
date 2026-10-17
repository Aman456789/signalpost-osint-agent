import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DataTable } from "@/components/DataTable";

const columns = [{ key: "name", header: "Name", sortKey: "name", render: (r) => r.name }];
const base = {
  columns,
  rows: [],
  rowKey: (r) => r.id,
  caption: "People",
  emptyTitle: "Nothing here",
};

describe("DataTable", () => {
  it("shows a loading state", () => {
    render(<DataTable {...base} loading />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
  });

  it("shows an error with a retry button", () => {
    const onRetry = vi.fn();
    render(<DataTable {...base} error="Cannot reach the agent service." onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Cannot reach the agent service.");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("shows an empty state", () => {
    render(<DataTable {...base} emptyText="Try another filter." />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    expect(screen.getByText("Try another filter.")).toBeInTheDocument();
  });

  it("sorts, filters and loads more", () => {
    const onSortChange = vi.fn();
    const onFilter = vi.fn();
    const onLoadMore = vi.fn();
    render(
      <DataTable
        {...base}
        rows={[{ id: "1", name: "Ada" }]}
        sort={{ key: "name", order: "asc" }}
        onSortChange={onSortChange}
        filter={{ label: "Search", placeholder: "Name", value: "", onChange: onFilter }}
        hasMore
        onLoadMore={onLoadMore}
      />,
    );
    expect(screen.getByText("Ada")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /Name/ })).toHaveAttribute("aria-sort", "ascending");

    fireEvent.click(screen.getByRole("button", { name: /Name/ }));
    expect(onSortChange).toHaveBeenCalledWith("name");

    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "ad" } });
    expect(onFilter).toHaveBeenCalledWith("ad");

    fireEvent.click(screen.getByRole("button", { name: "Load more" }));
    expect(onLoadMore).toHaveBeenCalledOnce();
  });
});
