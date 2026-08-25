"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCustomer, useCustomerOrders, useDeleteCustomer } from "../../../../../hooks/useCustomers";
import { useCan } from "../../../../../lib/rbac";
import { EmptyState } from "../../../../../components/ui/EmptyState";
import { AppError } from "../../../../../lib/api/errors";

export function CustomerDetailContent({ id }: { id: number }) {
  const router = useRouter();
  const customer = useCustomer(id);
  const orders = useCustomerOrders(id);
  const deleteCustomer = useDeleteCustomer();
  const canUpdate = useCan("customers:update");
  const canDelete = useCan("customers:delete");
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  if (customer.isPending) {
    return (
      <div className="flex flex-col gap-3 pt-4" aria-busy="true">
        <div className="h-6 w-48 animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
        <div className="h-32 w-full animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
      </div>
    );
  }

  if (customer.isError) {
    if (customer.error instanceof AppError && customer.error.status === 404) {
      return <EmptyState title="Customer not found" description={`No customer exists with ID ${id}.`} />;
    }
    return (
      <p className="pt-4 text-[13px] text-[var(--color-danger)]">
        {customer.error instanceof AppError ? customer.error.message : "Could not load this customer."}
      </p>
    );
  }

  if (!customer.data) {
    return <EmptyState title="Customer not found" description={`No customer exists with ID ${id}.`} />;
  }

  async function handleDelete() {
    setDeleteError(null);
    try {
      await deleteCustomer.mutateAsync(id);
      router.push("/sales/customers");
    } catch (err) {
      setDeleteError(
        err instanceof AppError ? err.message : "Something went wrong. Please try again.",
      );
      setConfirmingDelete(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 pt-4">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-[20px] text-[var(--color-text-hi)]">{customer.data.name}</h1>
          <p className="font-mono text-[13px] text-[var(--color-text-mid)]" data-numeric>
            #{customer.data.id}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {canUpdate && (
            <Link
              href={`/sales/customers/${id}/edit`}
              className="rounded-[6px] border border-[var(--color-hairline)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] transition-colors duration-150 hover:border-[var(--color-hairline-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
            >
              Edit
            </Link>
          )}
          {canDelete && !confirmingDelete && (
            <button
              type="button"
              onClick={() => setConfirmingDelete(true)}
              className="rounded-[6px] border border-[var(--color-danger)] px-3 py-1.5 text-[13px] text-[var(--color-danger)] transition-colors duration-150 hover:bg-[var(--color-danger)] hover:text-[var(--color-canvas)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
            >
              Delete
            </button>
          )}
          {canDelete && confirmingDelete && (
            <div className="flex items-center gap-2 text-[13px]">
              <span className="text-[var(--color-text-mid)]">Delete this customer?</span>
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleteCustomer.isPending}
                className="rounded-[6px] bg-[var(--color-danger)] px-3 py-1.5 text-[var(--color-canvas)] disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
              >
                {deleteCustomer.isPending ? "Deleting…" : "Confirm"}
              </button>
              <button
                type="button"
                onClick={() => setConfirmingDelete(false)}
                className="rounded-[6px] border border-[var(--color-hairline)] px-3 py-1.5 text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>

      {deleteError && (
        <p role="alert" className="text-[13px] text-[var(--color-danger)]">
          {deleteError}
        </p>
      )}

      <div className="grid grid-cols-2 gap-4 rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
        <div>
          <div className="text-[13px] text-[var(--color-text-mid)]">Email</div>
          <div className="font-mono text-[14px] text-[var(--color-text-hi)]">{customer.data.email ?? "—"}</div>
        </div>
        <div>
          <div className="text-[13px] text-[var(--color-text-mid)]">Phone</div>
          <div className="font-mono text-[14px] text-[var(--color-text-hi)]">{customer.data.phone ?? "—"}</div>
        </div>
        <div>
          <div className="text-[13px] text-[var(--color-text-mid)]">Country</div>
          <div className="font-mono text-[14px] text-[var(--color-text-hi)]">{customer.data.country ?? "—"}</div>
        </div>
        <div>
          <div className="text-[13px] text-[var(--color-text-mid)]">Created</div>
          <div className="font-mono text-[14px] text-[var(--color-text-hi)]" data-numeric>
            {new Date(customer.data.created_at).toLocaleString("en-GB")}
          </div>
        </div>
      </div>

      <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
        <h2 className="mb-2 text-[16px] font-medium text-[var(--color-text-hi)]">Orders</h2>
        {orders.isPending ? (
          <div className="h-16 w-full animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
        ) : orders.isError ? (
          <p className="text-[13px] text-[var(--color-danger)]">Could not load orders.</p>
        ) : orders.data && orders.data.length > 0 ? (
          <p className="text-[13px] text-[var(--color-text-mid)]">{orders.data.length} order(s) found.</p>
        ) : (
          <p className="text-[13px] text-[var(--color-text-mid)]">No orders yet.</p>
        )}
      </div>
    </div>
  );
}