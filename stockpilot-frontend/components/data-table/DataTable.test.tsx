import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DataTable, type DataTableColumn } from "./DataTable";

// BUILD.md Stage 0: "built against one dummy resource first, not yet
// wired to real endpoints." This dummy resource proves the primitive's
// contract (config-driven columns, sort callback, numeric alignment,
// empty state) before any real resource (Stage 2's Inventory) uses it.
interface DummyWidget {
  id: number;
  name: string;
  quantity: number;
}

const columns: DataTableColumn<DummyWidget>[] = [
  { key: "name", header: "Name", render: (row) => row.name },
  {
    key: "quantity",
    header: "Quantity",
    numeric: true,
    sortable: true,
    render: (row) => row.quantity,
  },
];

const rows: DummyWidget[] = [
  { id: 1, name: "Widget A", quantity: 10 },
  { id: 2, name: "Widget B", quantity: 5 },
];

describe("DataTable", () => {
  it("renders a header per column and a row per data item", () => {
    render(<DataTable columns={columns} rows={rows} getRowId={(row) => row.id} />);

    expect(screen.getByRole("columnheader", { name: "Name" })).toBeInTheDocument();
    expect(screen.getByText("Widget A")).toBeInTheDocument();
    expect(screen.getByText("Widget B")).toBeInTheDocument();
  });

  it("right-aligns and monospaces numeric columns", () => {
    render(<DataTable columns={columns} rows={rows} getRowId={(row) => row.id} />);

    const cell = screen.getByText("10");
    expect(cell).toHaveAttribute("data-numeric", "true");
  });

  it("calls onSortChange with the column key when a sortable header is clicked", async () => {
    const user = userEvent.setup();
    const onSortChange = vi.fn();
    render(
      <DataTable
        columns={columns}
        rows={rows}
        getRowId={(row) => row.id}
        onSortChange={onSortChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Quantity" }));

    expect(onSortChange).toHaveBeenCalledWith("quantity");
  });

  it("renders the caller-provided empty state instead of an empty table when rows is empty", () => {
    render(
      <DataTable
        columns={columns}
        rows={[]}
        getRowId={(row) => row.id}
        emptyState={<p>No widgets yet.</p>}
      />,
    );

    expect(screen.getByText("No widgets yet.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("does not use the empty state while isLoading is true, even with zero rows", () => {
    render(
      <DataTable
        columns={columns}
        rows={[]}
        getRowId={(row) => row.id}
        emptyState={<p>No widgets yet.</p>}
        isLoading
      />,
    );

    expect(screen.queryByText("No widgets yet.")).not.toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
  });
});
