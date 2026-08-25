"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useProducts } from "../../../hooks/useProducts";
import { DataTable, type DataTableColumn } from "../../../components/data-table/DataTable";
import { EmptyState } from "../../../components/ui/EmptyState";
import { formatCurrencyPrecise } from "../../../lib/format";
import { useCan } from "../../../lib/rbac";
import type { Product } from "../../../lib/validation/products";
import { AppError } from "../../../lib/api/errors";

const PAGE_SIZE = 50;

const columns: DataTableColumn<Product>[] = [
  { key: "sku", header: "SKU", render: (row) => row.sku },
  { key: "description", header: "Description", render: (row) => row.description ?? "—" },
  {
    key: "unit_cost",
    header: "Cost price",
    numeric: true,
    render: (row) => (row.unit_cost === null ? "—" : formatCurrencyPrecise(row.unit_cost)),
  },
  {
    key: "sale_price",
    header: "Sale price",
    numeric: true,
    render: (row) => (row.sale_price === null ? "—" : formatCurrencyPrecise(row.sale_price)),
  },
];

export function ProductsContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const canCreate = useCan("products:create");

  // docs/PRODUCT-SPEC.md §19: filter/sort state reflected in the URL.
  const search = searchParams.get("search") ?? "";
  const category = searchParams.get("category") ?? "";
  const page = Number(searchParams.get("page") ?? "1");

  const [searchInput, setSearchInput] = useState(search);
  const [categoryInput, setCategoryInput] = useState(category);

  const { data, isPending, isError, error } = useProducts({
    search: search || undefined,
    category: category || undefined,
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

  const hasFilters = Boolean(search || category);

  return (
    <div className="flex flex-col gap-4 pt-4">
      <div className="flex items-center justify-between">
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
          <button
            type="submit"
            className="rounded-[6px] border border-[var(--color-hairline)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] transition-colors duration-150 hover:border-[var(--color-hairline-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
          >
            Apply
          </button>
        </form>
        {canCreate && (
          <Link
            href="/products/new"
            className="rounded-[6px] bg-[var(--color-accent)] px-3 py-1.5 text-[13px] text-[var(--color-canvas)] transition-colors duration-150 hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
          >
            New product
          </Link>
        )}
      </div>

      {isError ? (
        <p className="text-[13px] text-[var(--color-danger)]">
          {error instanceof AppError ? error.message : "Could not load products."}
        </p>
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={data ?? []}
            getRowId={(row) => row.sku}
            isLoading={isPending}
            onRowClick={(row) => router.push(`/products/${encodeURIComponent(row.sku)}`)}
            emptyState={
              <EmptyState
                title={hasFilters ? "No products match these filters" : "No products yet"}
                description={
                  hasFilters
                    ? "Try clearing a filter to see more results."
                    : "Add your first product to start building your catalog."
                }
                action={
                  !hasFilters && canCreate ? (
                    <Link
                      href="/products/new"
                      className="rounded-[6px] bg-[var(--color-accent)] px-3 py-1.5 text-[13px] text-[var(--color-canvas)] hover:opacity-90"
                    >
                      Add your first product
                    </Link>
                  ) : undefined
                }
              />
            }
          />
          {data && data.length > 0 && (
            // GET /products returns a bare array with no total-count field,
            // same constraint as InventoryContent.tsx -- Next only enables
            // when the current page came back full.
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
        Product images supported via Cloudinary storage integration.
      </p>
    </div>
  );
}

