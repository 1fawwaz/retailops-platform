"use client";

import { useState } from "react";
import { useRoles, useCreateRole, useUpdateRole } from "../../../../hooks/useRoles";
import { DataTable, type DataTableColumn } from "../../../../components/data-table/DataTable";
import { EmptyState } from "../../../../components/ui/EmptyState";
import { useCan } from "../../../../lib/rbac";
import { AppError } from "../../../../lib/api/errors";
import type { Role } from "../../../../lib/validation/roles";

const ALL_PERMISSIONS = [
  "dashboard:read", "dashboard:create", "dashboard:update", "dashboard:delete", "dashboard:receive",
  "products:read", "products:create", "products:update", "products:delete", "products:receive",
  "inventory:read", "inventory:create", "inventory:update", "inventory:delete", "inventory:receive",
  "suppliers:read", "suppliers:create", "suppliers:update", "suppliers:delete", "suppliers:receive",
  "purchase_order:read", "purchase_order:create", "purchase_order:update", "purchase_order:delete", "purchase_order:receive",
  "sales:read", "sales:create", "sales:update", "sales:delete", "sales:receive",
  "customers:read", "customers:create", "customers:update", "customers:delete", "customers:receive",
  "forecasts:read", "forecasts:create", "forecasts:update", "forecasts:delete", "forecasts:receive",
  "analytics:read", "analytics:create", "analytics:update", "analytics:delete", "analytics:receive",
  "reports:read", "reports:create", "reports:update", "reports:delete", "reports:receive",
  "notifications:read", "notifications:create", "notifications:update", "notifications:delete", "notifications:receive",
  "audit_logs:read", "audit_logs:create", "audit_logs:update", "audit_logs:delete", "audit_logs:receive",
  "settings:read", "settings:create", "settings:update", "settings:delete", "settings:receive",
  "users:read", "users:create", "users:update", "users:delete", "users:receive",
  "roles:read", "roles:create", "roles:update", "roles:delete", "roles:receive",
  "profile:read", "profile:create", "profile:update", "profile:delete", "profile:receive",
];

const columns: DataTableColumn<Role>[] = [
  { key: "id", header: "ID", numeric: true, render: (row) => <span data-numeric className="font-mono">#{row.id}</span> },
  { key: "name", header: "Name", render: (row) => row.name },
  { key: "permissions", header: "Permissions", render: (row) => row.permissions.length > 0 ? row.permissions.join(", ") : "—" },
  { key: "created_at", header: "Created", render: (row) => new Date(row.created_at).toLocaleDateString("en-GB") },
];

export function RolesSettingsContent() {
  const [page, setPage] = useState(1);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [formValues, setFormValues] = useState({ name: "", permissions: [] as string[] });
  const PAGE_SIZE = 50;

  const canCreate = useCan("roles:create");
  const canUpdate = useCan("roles:update");
  const createRole = useCreateRole();
  const updateRole = useUpdateRole();
  const { data, isPending, isError, error } = useRoles({ limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE });

  function handlePermissionToggle(permission: string) {
    setFormValues((prev) => ({
      ...prev,
      permissions: prev.permissions.includes(permission)
        ? prev.permissions.filter((p) => p !== permission)
        : [...prev.permissions, permission],
    }));
  }

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    try {
      await createRole.mutateAsync(formValues);
      setShowCreateModal(false);
      setFormValues({ name: "", permissions: [] });
    } catch {
      // Error handled by form
    }
  }

  async function handleUpdate() {
    if (!editingRole) return;
    try {
      await updateRole.mutateAsync({ id: editingRole.id, values: formValues });
      setEditingRole(null);
      setFormValues({ name: "", permissions: [] });
    } catch {
      // Error handled by form
    }
  }

  function openEdit(role: Role) {
    setEditingRole(role);
    setFormValues({ name: role.name, permissions: [...role.permissions] });
  }

  return (
    <div className="flex flex-col gap-4 pt-4">
      <div className="flex items-center justify-between">
        <h1 className="text-[20px] text-[var(--color-text-hi)]">Roles</h1>
        {canCreate && (
          <button
            type="button"
            onClick={() => { setFormValues({ name: "", permissions: [] }); setShowCreateModal(true); }}
            className="rounded-[6px] bg-[var(--color-accent)] px-3 py-1.5 text-[13px] text-[var(--color-canvas)] transition-colors duration-150 hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
          >
            Add role
          </button>
        )}
      </div>

      {isError ? (
        <p className="text-[13px] text-[var(--color-danger)]">
          {error instanceof AppError ? error.message : "Could not load roles."}
        </p>
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={data ?? []}
            getRowId={(row) => row.id}
            isLoading={isPending}
            onRowClick={canUpdate ? openEdit : undefined}
            emptyState={
              <EmptyState
                title="No roles"
                description="No roles defined yet."
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

      {(showCreateModal || editingRole) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="rounded-[6px] bg-[var(--color-surface)] p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto">
            <h2 className="mb-4 text-[18px] font-medium text-[var(--color-text-hi)]">
              {editingRole ? "Edit role" : "Add role"}
            </h2>
            <form onSubmit={editingRole ? handleUpdate : handleCreate} className="flex flex-col gap-3">
              <div>
                <label htmlFor="name" className="mb-1 block text-[13px] text-[var(--color-text-mid)]">
                  Role Name
                </label>
                <input
                  id="name"
                  value={formValues.name}
                  onChange={(event) => setFormValues({ ...formValues, name: event.target.value })}
                  required
                  className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-canvas)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
                />
              </div>
              <div>
                <label className="mb-1 block text-[13px] text-[var(--color-text-mid)]">Permissions</label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-60 overflow-y-auto p-2 border border-[var(--color-hairline)] rounded-[6px]">
                  {ALL_PERMISSIONS.map((permission) => (
                    <label key={permission} className="flex items-center gap-2 text-[12px] text-[var(--color-text-hi)]">
                      <input
                        type="checkbox"
                        checked={formValues.permissions.includes(permission)}
                        onChange={() => handlePermissionToggle(permission)}
                        className="rounded-[4px] border border-[var(--color-hairline)]"
                      />
                      <span>{permission}</span>
                    </label>
                  ))}
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => { setShowCreateModal(false); setEditingRole(null); setFormValues({ name: "", permissions: [] }); }}
                  className="rounded-[6px] border border-[var(--color-hairline)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createRole.isPending || updateRole.isPending}
                  className="rounded-[6px] bg-[var(--color-accent)] px-3 py-1.5 text-[13px] text-[var(--color-canvas)] disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
                >
                  {(createRole.isPending || updateRole.isPending) ? "Saving…" : editingRole ? "Save changes" : "Create role"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}