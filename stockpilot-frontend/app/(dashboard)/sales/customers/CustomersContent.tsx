"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useCustomers } from "../../../../hooks/useCustomers";
import { DataTable, type DataTableColumn } from "../../../../components/data-table/DataTable";
import { EmptyState } from "../../../../components/ui/EmptyState";
import { useCan } from "../../../../lib/rbac";
import type { Customer } from "../../../../lib/validation/customers";
import { AppError } from "../../../../lib/api/errors";

const PAGE_SIZE = 50;

const columns: DataTableColumn<Customer>[] = [
  { key: "id", header: "ID", numeric: true, render: (row) => <span data-numeric className="font-mono">#{row.id}</span> },
  { key: "name", header: "Name", render: (row) => row.name },
  { key: "email", header: "Email", render: (row) => row.email ?? "—" },
  { key: "phone", header: "Phone", render: (row) => row.phone ?? "—" },
  { key: "country", header: "Country", render: (row) => row.country ?? "—" },
];

export function CustomersContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const canCreate = useCan("customers:create");

  const search = searchParams.get("search") ?? "";
  const page = Number(searchParams.get("page") ?? "1");

  const [searchInput, setSearchInput] = useState(search);

  const { data, isPending, isError, error } = useCustomers({
    search: search || undefined,
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
    updateParams({ search: searchInput, page: null });
  }

  const hasFilters = Boolean(search);

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
              placeholder="Name or email"
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
            href="/sales/customers/new"
            className="rounded-[6px] bg-[var(--color-accent)] px-3 py-1.5 text-[13px] text-[var(--color-canvas)] transition-colors duration-150 hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
          >
            New customer
          </Link>
        )}
      </div>

      {isError ? (
        <p className="text-[13px] text-[var(--color-danger)]">
          {error instanceof AppError ? error.message : "Could not load customers."}
        </p>
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={data ?? []}
            getRowId={(row) => row.id}
            isLoading={isPending}
            onRowClick={(row) => router.push(`/sales/customers/${row.id}`)}
            emptyState={
              <EmptyState
                title={hasFilters ? "No customers match these filters" : "No customers yet"}
                description={
                  hasFilters
                    ? "Try clearing the search to see more results."
                    : "Add your first customer to start building your customer base."
                }
                action={
                  !hasFilters && canCreate ? (
                    <Link
                      href="/sales/customers/new"
                      className="rounded-[6px] bg-[var(--color-accent)] px-3 py-1.5 text-[13px] text-[var(--color-canvas)] hover:opacity-90"
                    >
                      Add your first customer
                    </Link>
                  ) : undefined
                }
              />
            }
          />
          {data && data.length > 0 && (
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
    </div>
  );
}