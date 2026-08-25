"use client";

import { useState } from "react";
import { useAuditLogs } from "../../../hooks/useAuditLogs";
import { DataTable, type DataTableColumn } from "../../../components/data-table/DataTable";
import { EmptyState } from "../../../components/ui/EmptyState";
import { AppError } from "../../../lib/api/errors";
import type { AuditLog } from "../../../lib/validation/auditLogs";

const columns: DataTableColumn<AuditLog>[] = [
  { key: "id", header: "ID", numeric: true, render: (row) => <span data-numeric className="font-mono">#{row.id}</span> },
  { key: "user_id", header: "User", numeric: true, render: (row) => <span data-numeric className="font-mono">#{row.user_id}</span> },
  { key: "permission", header: "Permission", render: (row) => row.permission },
  { key: "method", header: "Method", render: (row) => row.method },
  { key: "path", header: "Path", render: (row) => <code className="text-[12px] font-mono">{row.path}</code> },
  { key: "outcome", header: "Outcome", render: (row) => (
    <span className={row.outcome === "granted" ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"}>
      {row.outcome}
    </span>
  )},
  { key: "created_at", header: "Created", render: (row) => new Date(row.created_at).toLocaleString("en-GB") },
];

export function AuditLogsContent() {
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({
    user_id: "",
    permission: "",
    outcome: "",
    date_from: "",
    date_to: "",
  });
  const PAGE_SIZE = 50;

  const { data, isPending, isError, error } = useAuditLogs({
    user_id: filters.user_id ? Number(filters.user_id) : undefined,
    permission: filters.permission || undefined,
    outcome: filters.outcome || undefined,
    date_from: filters.date_from || undefined,
    date_to: filters.date_to || undefined,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  });

  function handleFilterSubmit(event: React.FormEvent) {
    event.preventDefault();
    setPage(1);
  }

  return (
    <div className="flex flex-col gap-4 pt-4">
      <h1 className="text-[20px] text-[var(--color-text-hi)]">Audit Logs</h1>
      <p className="text-[13px] text-[var(--color-text-mid)]">
        Chronological record of all permission-gated actions. Admin only.
      </p>

      <form onSubmit={handleFilterSubmit} className="flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="user_id" className="mb-1 block text-[13px] text-[var(--color-text-mid)]">
            User ID
          </label>
          <input
            id="user_id"
            type="number"
            value={filters.user_id}
            onChange={(event) => setFilters({ ...filters, user_id: event.target.value })}
            placeholder="e.g. 1"
            className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-canvas)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
          />
        </div>
        <div>
          <label htmlFor="permission" className="mb-1 block text-[13px] text-[var(--color-text-mid)]">
            Permission
          </label>
          <input
            id="permission"
            value={filters.permission}
            onChange={(event) => setFilters({ ...filters, permission: event.target.value })}
            placeholder="e.g. purchase_order:update"
            className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-canvas)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
          />
        </div>
        <div>
          <label htmlFor="outcome" className="mb-1 block text-[13px] text-[var(--color-text-mid)]">
            Outcome
          </label>
          <select
            id="outcome"
            value={filters.outcome}
            onChange={(event) => setFilters({ ...filters, outcome: event.target.value })}
            className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-canvas)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
          >
            <option value="">All</option>
            <option value="granted">Granted</option>
            <option value="denied">Denied</option>
          </select>
        </div>
        <div>
          <label htmlFor="date_from" className="mb-1 block text-[13px] text-[var(--color-text-mid)]">
            From
          </label>
          <input
            id="date_from"
            type="date"
            value={filters.date_from}
            onChange={(event) => setFilters({ ...filters, date_from: event.target.value })}
            className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-canvas)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
          />
        </div>
        <div>
          <label htmlFor="date_to" className="mb-1 block text-[13px] text-[var(--color-text-mid)]">
            To
          </label>
          <input
            id="date_to"
            type="date"
            value={filters.date_to}
            onChange={(event) => setFilters({ ...filters, date_to: event.target.value })}
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

      {isError ? (
        <p className="text-[13px] text-[var(--color-danger)]">
          {error instanceof AppError ? error.message : "Could not load audit logs."}
        </p>
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={data ?? []}
            getRowId={(row) => row.id}
            isLoading={isPending}
            emptyState={
              <EmptyState
                title="No audit logs"
                description="No entries match the current filters."
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
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="rounded-[6px] border border-[var(--color-hairline)] px-2 py-1 disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
                >
                  Previous
                </button>
                <button
                  type="button"
                  onClick={() => setPage((p) => p + 1)}
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