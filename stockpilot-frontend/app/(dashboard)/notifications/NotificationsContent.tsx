"use client";

import { useState } from "react";
import { useNotifications, useMarkAllNotificationsRead } from "../../../hooks/useNotifications";
import { DataTable, type DataTableColumn } from "../../../components/data-table/DataTable";
import { EmptyState } from "../../../components/ui/EmptyState";
import { AppError } from "../../../lib/api/errors";
import type { Notification } from "../../../lib/validation/notifications";

const columns: DataTableColumn<Notification>[] = [
  { key: "id", header: "ID", numeric: true, render: (row) => <span data-numeric className="font-mono">#{row.id}</span> },
  { key: "type", header: "Type", render: (row) => row.type },
  { key: "message", header: "Message", render: (row) => row.message },
  { key: "resource_type", header: "Resource", render: (row) => row.resource_type ?? "—" },
  { key: "resource_id", header: "Resource ID", render: (row) => row.resource_id ?? "—" },
  { key: "is_read", header: "Read", render: (row) => row.is_read ? "Yes" : "No" },
  { key: "created_at", header: "Created", render: (row) => new Date(row.created_at).toLocaleString("en-GB") },
];

export function NotificationsContent() {
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 50;

  const markAllRead = useMarkAllNotificationsRead();
  const { data, isPending, isError, error, refetch } = useNotifications({ limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE });

  async function handleMarkAllRead() {
    await markAllRead.mutateAsync();
    refetch();
  }

  const unreadCount = data?.filter((n) => !n.is_read).length ?? 0;

  return (
    <div className="flex flex-col gap-4 pt-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[20px] text-[var(--color-text-hi)]">Notifications</h1>
          <p className="text-[13px] text-[var(--color-text-mid)]">
            {unreadCount > 0 ? `${unreadCount} unread` : "All caught up"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {unreadCount > 0 && (
            <button
              type="button"
              onClick={handleMarkAllRead}
              disabled={markAllRead.isPending}
              className="rounded-[6px] border border-[var(--color-hairline)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] transition-colors duration-150 hover:border-[var(--color-hairline-hi)] disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
            >
              {markAllRead.isPending ? "Marking all read…" : "Mark all as read"}
            </button>
          )}
        </div>
      </div>

      {isError ? (
        <p className="text-[13px] text-[var(--color-danger)]">
          {error instanceof AppError ? error.message : "Could not load notifications."}
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
                title="No notifications"
                description="System-generated alerts will appear here."
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