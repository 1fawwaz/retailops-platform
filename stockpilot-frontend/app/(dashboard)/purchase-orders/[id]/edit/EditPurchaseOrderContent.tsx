"use client";

import { useRouter } from "next/navigation";
import { PurchaseOrderForm } from "../../PurchaseOrderForm";
import { usePurchaseOrder } from "../../../../../hooks/usePurchaseOrder";
import { useUpdatePurchaseOrder } from "../../../../../hooks/useUpdatePurchaseOrder";
import { useCan } from "../../../../../lib/rbac";
import { EmptyState } from "../../../../../components/ui/EmptyState";
import { AppError } from "../../../../../lib/api/errors";
import type { PurchaseOrderFormValues } from "../../../../../lib/validation/purchaseOrders";

export function EditPurchaseOrderContent({ poId }: { poId: number }) {
  const router = useRouter();
  const purchaseOrder = usePurchaseOrder(poId);
  const canUpdate = useCan("purchase_order:update");
  const updatePO = useUpdatePurchaseOrder(poId);

  if (!canUpdate) {
    return (
      <EmptyState
        title="You don't have permission to edit purchase orders"
        description="Ask an administrator to grant you the purchase_order:update permission."
      />
    );
  }

  if (purchaseOrder.isPending) {
    return (
      <div className="flex flex-col gap-3 pt-4" aria-busy="true">
        <div className="h-6 w-48 animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
        <div className="h-64 w-full max-w-md animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
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

  if (purchaseOrder.data.status !== "draft") {
    return (
      <EmptyState
        title="Cannot edit this purchase order"
        description="Purchase orders can only be edited while in Draft status."
      />
    );
  }

  const defaultValues: PurchaseOrderFormValues = {
    supplier_id: purchaseOrder.data.supplier_id,
    warehouse_id: purchaseOrder.data.warehouse_id,
    lines: purchaseOrder.data.lines.map((line) => ({
      sku: line.sku,
      quantity_ordered: line.quantity_ordered,
      unit_cost: line.unit_cost,
    })),
  };

  async function handleSubmit(values: PurchaseOrderFormValues) {
    await updatePO.mutateAsync({
      supplier_id: values.supplier_id,
      warehouse_id: values.warehouse_id,
      lines: values.lines.map((line) => ({
        sku: line.sku,
        quantity_ordered: line.quantity_ordered,
        unit_cost: line.unit_cost,
      })),
    });
    router.push(`/purchase-orders/${poId}`);
  }

  return (
    <div className="flex flex-col gap-4 pt-4">
      <h1 className="text-[20px] text-[var(--color-text-hi)]">Edit purchase order #{poId}</h1>
      <PurchaseOrderForm
        defaultValues={defaultValues}
        submitLabel="Save changes"
        onSubmit={handleSubmit}
      />
    </div>
  );
}