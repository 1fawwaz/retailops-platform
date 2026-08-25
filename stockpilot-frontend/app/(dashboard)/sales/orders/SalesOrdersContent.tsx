"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useSalesOrders } from "../../../../hooks/useSalesOrders";
import { DataTable, type DataTableColumn } from "../../../../components/data-table/DataTable";
import { EmptyState } from "../../../../components/ui/EmptyState";
import { useCan } from "../../../../lib/rbac";
import type { SalesOrder } from "../../../../lib/validation/salesOrders";
import { AppError } from "../../../../lib/api/errors";

const PAGE_SIZE = 50;

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  confirmed: "Confirmed",
  fulfilled: "Fulfilled",
  cancelled: "Cancelled",
};

function statusBadge(status: string) {
  const label = STATUS_LABELS[status] ?? status;
  const base = "inline-flex items-center rounded-[6px] px-2 py-0.5 text-[11px] font-medium";
  const variants: Record<string, string> = {
    draft: "bg-[var(--color-surface)] border border-[var(--color-hairline)] text-[var(--color-text-hi)]",
    confirmed: "bg-[var(--color-accent)]/10 border border-[var(--color-accent)] text-[var(--color-accent)]",
    fulfilled: "bg-[var(--color-success)]/10 border border-[var(--color-success)] text-[var(--color-success)]",
    cancelled: "bg-[var(--color-danger)]/10 border border-[var(--color-danger)] text-[var(--color-danger)]",
  };
  return (
    <span className={`${base} ${variants[status] ?? variants.draft}`}>
      {label}
    </span>
  );
}

const columns: DataTableColumn<SalesOrder>[] = [
  {
    key: "id",
    header: "Order",
    numeric: true,
    render: (row) => <span data-numeric className="font-mono">#{row.id}</span>,
  },
  {
    key: "customer_id",
    header: "Customer",
    numeric: true,
    render: (row) => <span data-numeric className="font-mono">#{row.customer_id}</span>,
  },
  {
    key: "warehouse_id",
    header: "Warehouse",
    numeric: true,
    render: (row) => <span data-numeric className="font-mono">#{row.warehouse_id}</span>,
  },
  {
    key: "status",
    header: "Status",
    render: (row) => statusBadge(row.status),
  },
  {
    key: "created_at",
    header: "Created",
    render: (row) => new Date(row.created_at).toLocaleDateString("en-GB"),
  },
];

export function SalesOrdersContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const canCreate = useCan("sales:create");

  const status = searchParams.get("status") ?? "";
  const page = Number(searchParams.get("page") ?? "1");

  const [statusInput, setStatusInput] = useState(status);

  const { data, isPending, isError, error } = useSalesOrders({
    status: status || undefined,
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
    updateParams({ status: statusInput, page: null });
  }

  return (
    <div className="flex flex-col gap-4 pt-4">
      <div className="flex items-center justify-between">
        <form onSubmit={handleFilterSubmit} className="flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="status" className="mb-1 block text-[13px] text-[var(--color-text-mid)]">
              Status
            </label>
            <select
              id="status"
              value={statusInput}
              onChange={(event) => setStatusInput(event.target.value)}
              className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-canvas)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
            >
              <option value="">All</option>
              <option value="draft">Draft</option>
              <option value="confirmed">Confirmed</option>
              <option value="fulfilled">Fulfilled</option>
              <option value="cancelled">Cancelled</option>
            </select>
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
            href="/sales/orders/new"
            className="rounded-[6px] bg-[var(--color-accent)] px-3 py-1.5 text-[13px] text-[var(--color-canvas)] transition-colors duration-150 hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
          >
            New sales order
          </Link>
        )}
      </div>

      {isError ? (
        <p className="text-[13px] text-[var(--color-danger)]">
          {error instanceof AppError ? error.message : "Could not load sales orders."}
        </p>
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={data ?? []}
            getRowId={(row) => row.id}
            isLoading={isPending}
            onRowClick={(row) => router.push(`/sales/orders/${row.id}`)}
            emptyState={
              <EmptyState
                title={status ? `No sales orders with status "${STATUS_LABELS[status] ?? status}"` : "No sales orders yet"}
                description={
                  status
                    ? "Try clearing the status filter to see more results."
                    : "Create your first sales order to start tracking customer orders."
                }
                action={
                  !status && canCreate ? (
                    <Link
                      href="/sales/orders/new"
                      className="rounded-[6px] bg-[var(--color-accent)] px-3 py-1.5 text-[13px] text-[var(--color-canvas)] hover:opacity-90"
                    >
                      Create sales order
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