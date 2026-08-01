"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSupplier } from "../../../../hooks/useSupplier";
import { useSupplierRollup } from "../../../../hooks/useSupplierRollup";
import { useDeleteSupplier } from "../../../../hooks/useDeleteSupplier";
import { useCan } from "../../../../lib/rbac";
import { EmptyState } from "../../../../components/ui/EmptyState";
import { ProvenanceBadge, parseProvenance } from "../../../../components/ui/ProvenanceBadge";
import { formatCurrency, formatInteger } from "../../../../lib/format";
import { AppError } from "../../../../lib/api/errors";
import { SupplierContactsPanel } from "./SupplierContactsPanel";
import { SupplierPurchaseHistoryPanel } from "./SupplierPurchaseHistoryPanel";

function Field({ label, value, provenance }: { label: string; value: string; provenance?: string }) {
  const parsed = parseProvenance(provenance);
  return (
    <div>
      <div className="text-[13px] text-[var(--color-text-mid)]">{label}</div>
      <div className="font-mono text-[14px] text-[var(--color-text-hi)]" data-numeric>
        {value}
      </div>
      {parsed && <ProvenanceBadge provenance={parsed} />}
    </div>
  );
}

export function SupplierDetailContent({ supplierId }: { supplierId: number }) {
  const router = useRouter();
  const supplier = useSupplier(supplierId);
  const rollup = useSupplierRollup();
  const deleteSupplier = useDeleteSupplier();
  const canUpdate = useCan("suppliers:update");
  const canDelete = useCan("suppliers:delete");
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  if (supplier.isPending) {
    return (
      <div className="flex flex-col gap-3 pt-4" aria-busy="true">
        <div className="h-6 w-48 animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
        <div className="h-32 w-full animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
      </div>
    );
  }

  if (supplier.isError) {
    if (supplier.error instanceof AppError && supplier.error.status === 404) {
      return (
        <EmptyState title="Supplier not found" description={`No supplier exists with id ${supplierId}.`} />
      );
    }
    return (
      <p className="pt-4 text-[13px] text-[var(--color-danger)]">
        {supplier.error instanceof AppError ? supplier.error.message : "Could not load this supplier."}
      </p>
    );
  }

  if (!supplier.data) {
    return (
      <EmptyState title="Supplier not found" description={`No supplier exists with id ${supplierId}.`} />
    );
  }

  const rollupRow = rollup.data?.find((r) => r.supplier_id === supplierId);

  async function handleDelete() {
    setDeleteError(null);
    try {
      await deleteSupplier.mutateAsync(supplierId);
      router.push("/suppliers");
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
          <h1 className="text-[20px] text-[var(--color-text-hi)]">{supplier.data.name}</h1>
          <p className="font-mono text-[13px] text-[var(--color-text-mid)]" data-numeric>
            #{supplierId}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {canUpdate && (
            <Link
              href={`/suppliers/${supplierId}/edit`}
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
              <span className="text-[var(--color-text-mid)]">Delete this supplier?</span>
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleteSupplier.isPending}
                className="rounded-[6px] bg-[var(--color-danger)] px-3 py-1.5 text-[var(--color-canvas)] disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
              >
                {deleteSupplier.isPending ? "Deleting…" : "Confirm"}
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

      <div className="grid grid-cols-2 gap-4 rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4 sm:grid-cols-4">
        <Field
          label="Lead time"
          value={`${supplier.data.lead_time_days}d`}
          provenance={supplier.data._provenance.lead_time_days}
        />
        <Field
          label="Reliability score"
          value={supplier.data.reliability_score.toFixed(2)}
          provenance={supplier.data._provenance.reliability_score}
        />
        <Field label="SKUs supplied" value={formatInteger(supplier.data.skus.length)} />
        {rollup.isPending ? (
          <div className="h-10 w-24 animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
        ) : rollupRow ? (
          <Field
            label="On-time delivery"
            value={
              rollupRow.on_time_delivery_rate === null
                ? "No data"
                : `${(rollupRow.on_time_delivery_rate * 100).toFixed(0)}%`
            }
            provenance="derived"
          />
        ) : null}
      </div>

      {rollupRow && (
        <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
          <h2 className="mb-2 text-[16px] font-medium text-[var(--color-text-hi)]">Performance</h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Field label="Inventory value" value={formatCurrency(rollupRow.total_inventory_value)} provenance="derived" />
            <Field label="Open POs" value={formatInteger(rollupRow.open_purchase_order_count)} provenance="derived" />
            <Field label="Total POs" value={formatInteger(rollupRow.total_purchase_order_count)} provenance="derived" />
            <Field label="SKUs" value={formatInteger(rollupRow.sku_count)} provenance="derived" />
          </div>
          <p className="mt-3 text-[13px] text-[var(--color-text-mid)]">
            Defect/return rate is not tracked — StockPilot Core has no quality-inspection or return
            workflow.
          </p>
        </div>
      )}

      <SupplierContactsPanel supplierId={supplierId} canManage={canUpdate} />
      <SupplierPurchaseHistoryPanel supplierId={supplierId} />
    </div>
  );
}
