"use client";

import { useState } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useStock } from "../../../hooks/useStock";
import { DataTable, type DataTableColumn } from "../../../components/data-table/DataTable";
import { EmptyState } from "../../../components/ui/EmptyState";
import { formatInteger } from "../../../lib/format";
import { toCsv, downloadCsv } from "../../../lib/csv";
import type { StockItem } from "../../../lib/validation/inventory";
import { AppError } from "../../../lib/api/errors";

const PAGE_SIZE = 50;

const columns: DataTableColumn<StockItem>[] = [
  { key: "sku", header: "SKU", render: (row) => row.sku },
  { key: "description", header: "Description", render: (row) => row.description ?? "—" },
  { key: "category", header: "Category", render: (row) => row.category ?? "—" },
  {
    key: "quantity_on_hand",
    header: "On hand",
    numeric: true,
    render: (row) => formatInteger(row.quantity_on_hand),
  },
  {
    key: "reorder_point",
    header: "Reorder point",
    numeric: true,
    render: (row) => (row.reorder_point === null ? "—" : formatInteger(row.reorder_point)),
  },
  {
    key: "is_low_stock",
    header: "Status",
    render: (row) => (
      <span className={row.is_low_stock ? "text-[var(--color-danger)]" : "text-[var(--color-text-mid)]"}>
        {row.is_low_stock ? "Low stock" : "OK"}
      </span>
    ),
  },
];

export function InventoryContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // docs/PRODUCT-SPEC.md §19: "current search/filter/sort state...
  // reflected in the page's URL" -- read from and written to
  // searchParams directly, not local-only component state.
  const search = searchParams.get("search") ?? "";
  const category = searchParams.get("category") ?? "";
  const lowStockOnly = searchParams.get("low_stock") === "true";
  const page = Number(searchParams.get("page") ?? "1");

  const [searchInput, setSearchInput] = useState(search);
  const [categoryInput, setCategoryInput] = useState(category);

  const { data, isPending, isError, error } = useStock({
    search: search || undefined,
    category: category || undefined,
    lowStock: lowStockOnly || undefined,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  });

  function updateParams(next: Record<string, string | null>) {
    const params = new URLSearchParams(searchParams);
    for (const [key, value] of Object.entries(next)) {
      if (value === null || value === "") params.delete(key);
      else params.set(key, value);
    }
    router.push(`${pathname}?${params.toString()}`);
  }

  function handleFilterSubmit(event: React.FormEvent) {
    event.preventDefault();
    updateParams({ search: searchInput, category: categoryInput, page: null });
  }

  function handleExport() {
    if (!data) return;
    const csv = toCsv(data, [
      "sku",
      "description",
      "category",
      "quantity_on_hand",
      "reorder_point",
      "safety_stock",
      "is_low_stock",
      "as_of_date",
    ]);
    downloadCsv(`inventory-${new Date().toISOString().slice(0, 10)}.csv`, csv);
  }

  return (
    <div className="flex flex-col gap-4 pt-4">
      <form onSubmit={handleFilterSubmit} className="flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="search" className="mb-1 block text-[13px] text-[var(--color-text-mid)]">
            Search
          </label>
          <input
            id="search"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="SKU or description"
            className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-canvas)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
          />
        </div>
        <div>
          <label htmlFor="category" className="mb-1 block text-[13px] text-[var(--color-text-mid)]">
            Category
          </label>
          <input
            id="category"
            value={categoryInput}
            onChange={(event) => setCategoryInput(event.target.value)}
            placeholder="e.g. Decorations"
            className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-canvas)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
          />
        </div>
        <label className="flex items-center gap-2 pb-1.5 text-[13px] text-[var(--color-text-mid)]">
          <input
            type="checkbox"
            checked={lowStockOnly}
            onChange={(event) => updateParams({ low_stock: event.target.checked ? "true" : null, page: null })}
          />
          Low stock only
        </label>
        <button
          type="submit"
          className="rounded-[6px] border border-[var(--color-hairline)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] transition-colors duration-150 hover:border-[var(--color-hairline-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
        >
          Apply
        </button>
        <button
          type="button"
          onClick={handleExport}
          disabled={!data || data.length === 0}
          className="rounded-[6px] border border-[var(--color-hairline)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] transition-colors duration-150 hover:border-[var(--color-hairline-hi)] disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
        >
          Export CSV
        </button>
      </form>

      {isError ? (
        <p className="text-[13px] text-[var(--color-danger)]">
          {error instanceof AppError ? error.message : "Could not load inventory."}
        </p>
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={data ?? []}
            getRowId={(row) => row.sku}
            isLoading={isPending}
            onRowClick={(row) => router.push(`/inventory/${encodeURIComponent(row.sku)}`)}
            emptyState={
              <EmptyState
                title={search || category || lowStockOnly ? "No items match these filters" : "No inventory yet"}
                description={
                  search || category || lowStockOnly
                    ? "Try clearing a filter to see more results."
                    : "Inventory will appear here once StockPilot Core has stock data."
                }
              />
            }
          />
          {data && data.length > 0 && (
            // docs/stockpilot-gaps.md: /inventory/stock returns a bare
            // array with no total-count field -- components/data-table's
            // shared Pagination assumes a known total, which we don't
            // have here, so reusing it would either fabricate a total or
            // get the Next-button logic backwards. This is a deliberately
            // simpler, honest control: Next is only enabled when the
            // current page came back full (limit reached, more rows may
            // exist); a partial page is the real signal that this is the
            // last page, not a computed total.
            <div className="flex items-center justify-between px-1 py-3 text-[13px] text-[var(--color-text-mid)]">
              <span data-numeric className="font-mono">
                Showing {(page - 1) * PAGE_SIZE + 1}–{(page - 1) * PAGE_SIZE + data.length}
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => updateParams({ page: String(page - 1) })}
                  disabled={page <= 1}
                  className="rounded-[6px] border border-[var(--color-hairline)] px-2 py-1 disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
                >
                  Previous
                </button>
                <button
                  type="button"
                  onClick={() => updateParams({ page: String(page + 1) })}
                  disabled={data.length < PAGE_SIZE}
                  className="rounded-[6px] border border-[var(--color-hairline)] px-2 py-1 disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}

      <p className="text-[13px] text-[var(--color-text-mid)]">
        Warehouse/location filtering, supplier filtering, and bulk actions are not available —
        StockPilot Core has no location field and no inventory-mutation endpoint. See{" "}
        <code className="font-mono">docs/stockpilot-gaps.md</code>.
      </p>
    </div>
  );
}
