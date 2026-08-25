"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSalesOrder, useConfirmSalesOrder, useCancelSalesOrder, useFulfillSalesOrder } from "../../../../../hooks/useSalesOrders";
import { useCan } from "../../../../../lib/rbac";
import { EmptyState } from "../../../../../components/ui/EmptyState";
import { AppError } from "../../../../../lib/api/errors";
import { formatCurrencyPrecise } from "../../../../../lib/format";

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

export function SalesOrderDetailContent({ id }: { id: number }) {
  const router = useRouter();
  const order = useSalesOrder(id);
  const confirmOrder = useConfirmSalesOrder();
  const cancelOrder = useCancelSalesOrder();
  const fulfillOrder = useFulfillSalesOrder();
  const canUpdate = useCan("sales:update");
  const [actionError, setActionError] = useState<string | null>(null);

  if (order.isPending) {
    return (
      <div className="flex flex-col gap-3 pt-4" aria-busy="true">
        <div className="h-6 w-48 animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
        <div className="h-32 w-full animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
      </div>
    );
  }

  if (order.isError) {
    if (order.error instanceof AppError && order.error.status === 404) {
      return <EmptyState title="Order not found" description={`No order exists with ID ${id}.`} />;
    }
    return (
      <p className="pt-4 text-[13px] text-[var(--color-danger)]">
        {order.error instanceof AppError ? order.error.message : "Could not load this order."}
      </p>
    );
  }

  if (!order.data) {
    return <EmptyState title="Order not found" description={`No order exists with ID ${id}.`} />;
  }

  const data = order.data;

  async function handleConfirm() {
    setActionError(null);
    try {
      await confirmOrder.mutateAsync(id);
      order.refetch();
    } catch (err) {
      setActionError(err instanceof AppError ? err.message : "Could not confirm order.");
    }
  }

  async function handleCancel() {
    setActionError(null);
    try {
      await cancelOrder.mutateAsync(id);
      order.refetch();
    } catch (err) {
      setActionError(err instanceof AppError ? err.message : "Could not cancel order.");
    }
  }

  async function handleFulfill() {
    setActionError(null);
    try {
      await fulfillOrder.mutateAsync(id);
      order.refetch();
    } catch (err) {
      setActionError(err instanceof AppError ? err.message : "Could not fulfill order.");
    }
  }

  const canConfirm = data.status === "draft";
  const canCancel = data.status === "draft" || data.status === "confirmed";
  const canFulfill = data.status === "confirmed";

  return (
    <div className="flex flex-col gap-6 pt-4">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-[20px] text-[var(--color-text-hi)]">Sales Order #{data.id}</h1>
          <p className="font-mono text-[13px] text-[var(--color-text-mid)]" data-numeric>
            Customer #{data.customer_id} · Warehouse #{data.warehouse_id}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {statusBadge(data.status)}
        </div>
      </div>

      {actionError && (
        <p role="alert" className="text-[13px] text-[var(--color-danger)]">
          {actionError}
        </p>
      )}

      <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
        <h2 className="mb-3 text-[16px] font-medium text-[var(--color-text-hi)]">Actions</h2>
        <div className="flex flex-wrap gap-2">
          {canConfirm && canUpdate && (
            <button
              type="button"
              onClick={handleConfirm}
              disabled={confirmOrder.isPending}
              className="rounded-[6px] bg-[var(--color-accent)] px-3 py-1.5 text-[13px] text-[var(--color-canvas)] disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
            >
              {confirmOrder.isPending ? "Confirming…" : "Confirm"}
            </button>
          )}
          {canCancel && canUpdate && (
            <button
              type="button"
              onClick={handleCancel}
              disabled={cancelOrder.isPending}
              className="rounded-[6px] border border-[var(--color-danger)] px-3 py-1.5 text-[13px] text-[var(--color-danger)] hover:bg-[var(--color-danger)] hover:text-[var(--color-canvas)] disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
            >
              {cancelOrder.isPending ? "Cancelling…" : "Cancel"}
            </button>
          )}
          {canFulfill && canUpdate && (
            <button
              type="button"
              onClick={handleFulfill}
              disabled={fulfillOrder.isPending}
              className="rounded-[6px] bg-[var(--color-success)] px-3 py-1.5 text-[13px] text-[var(--color-canvas)] disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
            >
              {fulfillOrder.isPending ? "Fulfilling…" : "Fulfill"}
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4 sm:grid-cols-4">
        <div>
          <div className="text-[13px] text-[var(--color-text-mid)]">Customer</div>
          <div className="font-mono text-[14px] text-[var(--color-text-hi)]" data-numeric>#{data.customer_id}</div>
        </div>
        <div>
          <div className="text-[13px] text-[var(--color-text-mid)]">Warehouse</div>
          <div className="font-mono text-[14px] text-[var(--color-text-hi)]" data-numeric>#{data.warehouse_id}</div>
        </div>
        <div>
          <div className="text-[13px] text-[var(--color-text-mid)]">Created</div>
          <div className="font-mono text-[14px] text-[var(--color-text-hi)]" data-numeric>
            {new Date(data.created_at).toLocaleString("en-GB")}
          </div>
        </div>
        <div>
          <div className="text-[13px] text-[var(--color-text-mid)]">Updated</div>
          <div className="font-mono text-[14px] text-[var(--color-text-hi)]" data-numeric>
            {new Date(data.updated_at).toLocaleString("en-GB")}
          </div>
        </div>
      </div>

      <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
        <h2 className="mb-3 text-[16px] font-medium text-[var(--color-text-hi)]">Lines</h2>
        {data.lines && data.lines.length > 0 ? (
          <table className="w-full text-[13px]">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-[0.04em] text-[var(--color-text-mid)]">
                <th className="py-1 pr-3">SKU</th>
                <th className="py-1 pr-3 text-right" data-numeric>Quantity</th>
                <th className="py-1 pr-3 text-right" data-numeric>Unit Price</th>
                <th className="py-1 text-right" data-numeric>Total</th>
              </tr>
            </thead>
            <tbody>
              {data.lines.map((line, index) => (
                <tr key={index} className="border-t border-[var(--color-hairline)]">
                  <td className="py-1 pr-3 font-mono text-[var(--color-text-hi)]">{line.sku}</td>
                  <td className="py-1 pr-3 text-right font-mono text-[var(--color-text-hi)]" data-numeric>{line.quantity}</td>
                  <td className="py-1 pr-3 text-right font-mono text-[var(--color-text-hi)]" data-numeric>{formatCurrencyPrecise(line.unit_price)}</td>
                  <td className="py-1 text-right font-mono text-[var(--color-text-hi)]" data-numeric>{formatCurrencyPrecise(line.quantity * line.unit_price)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-[13px] text-[var(--color-text-mid)]">No lines.</p>
        )}
      </div>
    </div>
  );
}