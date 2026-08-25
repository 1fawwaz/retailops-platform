"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { usePurchaseOrder } from "../../../../hooks/usePurchaseOrder";
import { useSupplier } from "../../../../hooks/useSupplier";
import { useWarehouses } from "../../../../hooks/useWarehouses";
import { useCan } from "../../../../lib/rbac";
import { EmptyState } from "../../../../components/ui/EmptyState";
import { ProvenanceBadge, parseProvenance } from "../../../../components/ui/ProvenanceBadge";
import { formatCurrencyPrecise } from "../../../../lib/format";
import { AppError } from "../../../../lib/api/errors";
import { useSubmitPurchaseOrder } from "../../../../hooks/useSubmitPurchaseOrder";
import { useApprovePurchaseOrder } from "../../../../hooks/useApprovePurchaseOrder";
import { useCancelPurchaseOrder } from "../../../../hooks/useCancelPurchaseOrder";
import { useClosePurchaseOrder } from "../../../../hooks/useClosePurchaseOrder";
import { useReceivePurchaseOrder } from "../../../../hooks/useReceivePurchaseOrder";

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  submitted: "Submitted",
  approved: "Approved",
  partially_received: "Partially Received",
  received: "Received",
  closed: "Closed",
  cancelled: "Cancelled",
};

const STATUS_TRANSITIONS: Record<string, string[]> = {
  draft: ["submit", "cancel"],
  submitted: ["approve", "cancel"],
  approved: ["receive", "cancel"],
  partially_received: ["receive", "cancel"],
  received: ["close"],
  closed: [],
  cancelled: [],
};

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

function statusBadge(status: string) {
  const label = STATUS_LABELS[status] ?? status;
  const base = "inline-flex items-center rounded-[6px] px-2 py-0.5 text-[11px] font-medium";
  const variants: Record<string, string> = {
    draft: "bg-[var(--color-surface)] border border-[var(--color-hairline)] text-[var(--color-text-hi)]",
    submitted: "bg-[var(--color-accent)]/10 border border-[var(--color-accent)] text-[var(--color-accent)]",
    approved: "bg-[var(--color-success)]/10 border border-[var(--color-success)] text-[var(--color-success)]",
    partially_received: "bg-[var(--color-warning)]/10 border border-[var(--color-warning)] text-[var(--color-warning)]",
    received: "bg-[var(--color-success)]/10 border border-[var(--color-success)] text-[var(--color-success)]",
    closed: "bg-[var(--color-surface)] border border-[var(--color-hairline)] text-[var(--color-text-mid)]",
    cancelled: "bg-[var(--color-danger)]/10 border border-[var(--color-danger)] text-[var(--color-danger)]",
  };
  return (
    <span className={`${base} ${variants[status] ?? variants.draft}`}>
      {label}
    </span>
  );
}

export function PurchaseOrderDetailContent({ poId }: { poId: number }) {
  const router = useRouter();
  const purchaseOrder = usePurchaseOrder(poId);
  const supplier = useSupplier(purchaseOrder.data?.supplier_id ?? 0);
  const warehouses = useWarehouses();
  const canUpdate = useCan("purchase_order:update");
  const canReceive = useCan("purchase_order:receive");
  const canDelete = useCan("purchase_order:delete");
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const submitPO = useSubmitPurchaseOrder(poId);
  const approvePO = useApprovePurchaseOrder(poId);
  const cancelPO = useCancelPurchaseOrder(poId);
  const closePO = useClosePurchaseOrder(poId);
  const receivePO = useReceivePurchaseOrder(poId);
  const [receivingLineId, setReceivingLineId] = useState<number | null>(null);
  const [receiveQty, setReceiveQty] = useState("");
  const [receiveError, setReceiveError] = useState<string | null>(null);

  if (purchaseOrder.isPending) {
    return (
      <div className="flex flex-col gap-3 pt-4" aria-busy="true">
        <div className="h-6 w-48 animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
        <div className="h-32 w-full animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
      </div>
    );
  }

  if (purchaseOrder.isError) {
    if (purchaseOrder.error instanceof AppError && purchaseOrder.error.status === 404) {
      return <EmptyState title="Purchase order not found" description={`No purchase order exists with id ${poId}.`} />;
    }
    return (
      <p className="pt-4 text-[13px] text-[var(--color-danger)]">
        {purchaseOrder.error instanceof AppError ? purchaseOrder.error.message : "Could not load this purchase order."}
      </p>
    );
  }

  if (!purchaseOrder.data) {
    return <EmptyState title="Purchase order not found" description={`No purchase order exists with id ${poId}.`} />;
  }

  const warehouse = warehouses.data?.find((w) => w.id === purchaseOrder.data.warehouse_id);

  async function handleDelete() {
    setDeleteError(null);
    try {
      // Note: There's no delete PO endpoint in the API, so we just navigate away
      // In a real app, you'd call a delete endpoint here
      router.push("/purchase-orders");
    } catch (err) {
      setDeleteError(
        err instanceof AppError ? err.message : "Something went wrong. Please try again.",
      );
      setConfirmingDelete(false);
    }
  }

  async function handleTransition(action: string) {
    try {
      switch (action) {
        case "submit":
          await submitPO.mutateAsync();
          break;
        case "approve":
          await approvePO.mutateAsync();
          break;
        case "cancel":
          await cancelPO.mutateAsync();
          break;
        case "close":
          await closePO.mutateAsync();
          break;
      }
    } catch (err) {
      // Error handled by mutation
      console.error(err);
    }
  }

  async function handleReceive(lineId: number, qty: number) {
    setReceiveError(null);
    try {
      await receivePO.mutateAsync({
        lines: [{ line_id: lineId, quantity: qty, over_receipt_confirmed: false }],
      });
      setReceivingLineId(null);
      setReceiveQty("");
    } catch (err) {
      setReceiveError(
        err instanceof AppError ? err.message : "Something went wrong. Please try again.",
      );
    }
  }

  const availableActions = STATUS_TRANSITIONS[purchaseOrder.data.status] ?? [];

  return (
    <div className="flex flex-col gap-6 pt-4">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-[20px] text-[var(--color-text-hi)]">
            Purchase Order #{purchaseOrder.data.id}
          </h1>
          <p className="font-mono text-[13px] text-[var(--color-text-mid)]" data-numeric>
            {statusBadge(purchaseOrder.data.status)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {canUpdate && purchaseOrder.data.status === "draft" && (
            <Link
              href={`/purchase-orders/${poId}/edit`}
              className="rounded-[6px] border border-[var(--color-hairline)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] transition-colors duration-150 hover:border-[var(--color-hairline-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
            >
              Edit
            </Link>
          )}
          {/* Action buttons based on status */}
          {availableActions.map((action) => {
            const labels: Record<string, string> = {
              submit: "Submit",
              approve: "Approve",
              cancel: "Cancel",
              close: "Close",
              receive: "Receive",
            };
            const variants: Record<string, string> = {
              submit: "bg-[var(--color-accent)] text-[var(--color-canvas)]",
              approve: "bg-[var(--color-success)] text-[var(--color-canvas)]",
              cancel: "border border-[var(--color-danger)] text-[var(--color-danger)] hover:bg-[var(--color-danger)] hover:text-[var(--color-canvas)]",
              close: "border border-[var(--color-hairline)] text-[var(--color-text-hi)]",
              receive: "bg-[var(--color-warning)] text-[var(--color-canvas)]",
            };
            const simpleMutations: Record<string, typeof submitPO> = {
              submit: submitPO,
              approve: approvePO,
              cancel: cancelPO,
              close: closePO,
            };
            if (action === "receive") {
              return (
                <button
                  key={action}
                  type="button"
                  onClick={() => {
                    setReceivingLineId(purchaseOrder.data.lines[0]?.id ?? 0);
                  }}
                  disabled={receivePO.isPending}
                  className={`rounded-[6px] px-3 py-1.5 text-[13px] transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)] ${variants[action]}`}
                >
                  {receivePO.isPending ? "Receiving…" : labels[action]}
                </button>
              );
            }
            const mutation = simpleMutations[action];
            if (!mutation) return null;
            return (
              <button
                key={action}
                type="button"
                onClick={() => handleTransition(action)}
                disabled={mutation.isPending}
                className={`rounded-[6px] px-3 py-1.5 text-[13px] transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)] ${variants[action]}`}
              >
                {mutation.isPending ? `${labels[action]}…` : labels[action]}
              </button>
            );
          })}
          {canDelete && !confirmingDelete && purchaseOrder.data.status === "draft" && (
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
              <span className="text-[var(--color-text-mid)]">Delete this purchase order?</span>
              <button
                type="button"
                onClick={handleDelete}
                disabled={false} // No delete mutation yet
                className="rounded-[6px] bg-[var(--color-danger)] px-3 py-1.5 text-[var(--color-canvas)] disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
              >
                Confirm
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
          label="Supplier"
          value={supplier.data?.name ?? (purchaseOrder.data.supplier_id ? `#${purchaseOrder.data.supplier_id}` : "—")}
        />
        <Field
          label="Warehouse"
          value={warehouse?.name ?? (purchaseOrder.data.warehouse_id ? `#${purchaseOrder.data.warehouse_id}` : "—")}
        />
        <Field
          label="Created by"
          value={purchaseOrder.data.created_by_user_id ? `#${purchaseOrder.data.created_by_user_id}` : "—"}
        />
        <Field
          label="Created"
          value={new Date(purchaseOrder.data.created_at).toLocaleString("en-GB")}
        />
      </div>

      <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
        <h2 className="mb-2 text-[16px] font-medium text-[var(--color-text-hi)]">Lines</h2>
        {purchaseOrder.data.lines.length > 0 ? (
          <table className="w-full text-[13px]">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-[0.04em] text-[var(--color-text-mid)]">
                <th className="py-1 pr-3">SKU</th>
                <th className="py-1 pr-3 text-right">Ordered</th>
                <th className="py-1 pr-3 text-right">Received</th>
                <th className="py-1 pr-3 text-right">Remaining</th>
                <th className="py-1 pr-3 text-right">Unit cost</th>
                <th className="py-1">Actions</th>
              </tr>
            </thead>
            <tbody>
              {purchaseOrder.data.lines.map((line) => {
                const remaining = line.quantity_ordered - line.quantity_received;
                return (
                  <tr key={line.id} className="border-t border-[var(--color-hairline)]">
                    <td className="py-1 pr-3 font-mono text-[var(--color-text-hi)]" data-numeric>
                      {line.sku}
                    </td>
                    <td className="py-1 pr-3 text-right font-mono text-[var(--color-text-hi)]" data-numeric>
                      {line.quantity_ordered}
                    </td>
                    <td className="py-1 pr-3 text-right font-mono text-[var(--color-text-hi)]" data-numeric>
                      {line.quantity_received}
                    </td>
                    <td className="py-1 pr-3 text-right font-mono text-[var(--color-text-hi)]" data-numeric>
                      {remaining}
                    </td>
                    <td className="py-1 pr-3 text-right font-mono text-[var(--color-text-mid)]" data-numeric>
                      {line.unit_cost === null ? "—" : formatCurrencyPrecise(line.unit_cost)}
                    </td>
                    <td className="py-1">
                      {canReceive && remaining > 0 && purchaseOrder.data.status !== "draft" && (
                        <div className="flex items-center gap-2">
                          {receivingLineId === line.id ? (
                            <>
                              <input
                                type="number"
                                min="1"
                                max={remaining}
                                value={receiveQty}
                                onChange={(e) => setReceiveQty(e.target.value)}
                                className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-canvas)] px-2 py-1 text-[13px] text-[var(--color-text-hi)] w-20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
                              />
                              <button
                                type="button"
                                onClick={() => handleReceive(line.id, Number(receiveQty))}
                                disabled={receivePO.isPending || !receiveQty}
                                className="rounded-[6px] bg-[var(--color-accent)] px-2 py-1 text-[12px] text-[var(--color-canvas)] disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
                              >
                                Confirm
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  setReceivingLineId(null);
                                  setReceiveQty("");
                                  setReceiveError(null);
                                }}
                                className="rounded-[6px] border border-[var(--color-hairline)] px-2 py-1 text-[12px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
                              >
                                Cancel
                              </button>
                            </>
                          ) : (
                            <button
                              type="button"
                              onClick={() => {
                                setReceivingLineId(line.id);
                                setReceiveQty(String(remaining));
                              }}
                              className="rounded-[6px] border border-[var(--color-hairline)] px-2 py-1 text-[12px] text-[var(--color-text-hi)] hover:border-[var(--color-hairline-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
                            >
                              Receive
                            </button>
                          )}
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <p className="text-[13px] text-[var(--color-text-mid)]">No lines on this purchase order.</p>
        )}
        {receiveError && (
          <p role="alert" className="mt-2 text-[13px] text-[var(--color-danger)]">
            {receiveError}
          </p>
        )}
      </div>
    </div>
  );
}