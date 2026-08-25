"use client";

import { useState } from "react";
import Link from "next/link";
import { useUsers, useCreateUser, useAssignRole, useRevokeRole } from "../../../../hooks/useUsers";
import { DataTable, type DataTableColumn } from "../../../../components/data-table/DataTable";
import { EmptyState } from "../../../../components/ui/EmptyState";
import { useCan } from "../../../../lib/rbac";
import { AppError } from "../../../../lib/api/errors";
import type { UserWithRoles } from "../../../../lib/validation/users";

const columns: DataTableColumn<UserWithRoles>[] = [
  { key: "id", header: "ID", numeric: true, render: (row) => <span data-numeric className="font-mono">#{row.id}</span> },
  { key: "email", header: "Email", render: (row) => row.email },
  { key: "is_active", header: "Active", render: (row) => row.is_active ? "Yes" : "No" },
  { key: "is_read_only", header: "Read-only", render: (row) => row.is_read_only ? "Yes" : "No" },
  { key: "roles", header: "Roles", render: (row) => row.roles.length > 0 ? row.roles.join(", ") : "—" },
  { key: "created_at", header: "Created", render: (row) => new Date(row.created_at).toLocaleDateString("en-GB") },
];

export function UsersSettingsContent() {
  const [page, setPage] = useState(1);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState({ email: "", password: "", full_name: "" });
  const PAGE_SIZE = 50;

  const canCreate = useCan("users:create");
  const createUser = useCreateUser();
  const assignRole = useAssignRole();
  const revokeRole = useRevokeRole();
  const { data, isPending, isError, error } = useUsers({ limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE });

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    try {
      await createUser.mutateAsync(createForm);
      setShowCreateModal(false);
      setCreateForm({ email: "", password: "", full_name: "" });
    } catch (err) {
      // Error handled by form
    }
  }

  async function handleAssignRole(userId: number, roleId: number) {
    await assignRole.mutateAsync({ userId, roleId });
  }

  async function handleRevokeRole(userId: number, roleId: number) {
    await revokeRole.mutateAsync({ userId, roleId });
  }

  return (
    <div className="flex flex-col gap-4 pt-4">
      <div className="flex items-center justify-between">
        <h1 className="text-[20px] text-[var(--color-text-hi)]">Users</h1>
        {canCreate && (
          <button
            type="button"
            onClick={() => setShowCreateModal(true)}
            className="rounded-[6px] bg-[var(--color-accent)] px-3 py-1.5 text-[13px] text-[var(--color-canvas)] transition-colors duration-150 hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
          >
            Add user
          </button>
        )}
      </div>

      {isError ? (
        <p className="text-[13px] text-[var(--color-danger)]">
          {error instanceof AppError ? error.message : "Could not load users."}
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
                title="No users"
                description="No users found."
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

      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="rounded-[6px] bg-[var(--color-surface)] p-6 w-full max-w-md">
            <h2 className="mb-4 text-[18px] font-medium text-[var(--color-text-hi)]">Add User</h2>
            <form onSubmit={handleCreate} className="flex flex-col gap-3">
              <div>
                <label htmlFor="email" className="mb-1 block text-[13px] text-[var(--color-text-mid)]">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  value={createForm.email}
                  onChange={(event) => setCreateForm({ ...createForm, email: event.target.value })}
                  required
                  className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-canvas)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
                />
              </div>
              <div>
                <label htmlFor="password" className="mb-1 block text-[13px] text-[var(--color-text-mid)]">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  value={createForm.password}
                  onChange={(event) => setCreateForm({ ...createForm, password: event.target.value })}
                  required
                  minLength={8}
                  className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-canvas)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
                />
              </div>
              <div>
                <label htmlFor="full_name" className="mb-1 block text-[13px] text-[var(--color-text-mid)]">
                  Full Name (optional)
                </label>
                <input
                  id="full_name"
                  value={createForm.full_name}
                  onChange={(event) => setCreateForm({ ...createForm, full_name: event.target.value })}
                  className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-canvas)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
                />
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="rounded-[6px] border border-[var(--color-hairline)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createUser.isPending}
                  className="rounded-[6px] bg-[var(--color-accent)] px-3 py-1.5 text-[13px] text-[var(--color-canvas)] disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
                >
                  {createUser.isPending ? "Creating…" : "Create user"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}