"use client";

import { useRouter } from "next/navigation";
import { PurchaseOrderForm } from "../PurchaseOrderForm";
import { useCreatePurchaseOrder } from "../../../../hooks/useCreatePurchaseOrder";
import { useCan } from "../../../../lib/rbac";
import { EmptyState } from "../../../../components/ui/EmptyState";
import type { PurchaseOrderFormValues } from "../../../../lib/validation/purchaseOrders";

const FORM_DEFAULTS: PurchaseOrderFormValues = {
  supplier_id: 0,
  warehouse_id: 0,
  lines: [],
};

export function NewPurchaseOrderContent() {
  const router = useRouter();
  const canCreate = useCan("purchase_order:create");
  const createPO = useCreatePurchaseOrder();

  if (!canCreate) {
    return (
      <EmptyState
        title="You don't have permission to create purchase orders"
        description="Ask an administrator to grant you the purchase_order:create permission."
      />
    );
  }

  async function handleSubmit(values: PurchaseOrderFormValues) {
    await createPO.mutateAsync(values);
    // The mutation's onSuccess will invalidate queries
    // We need to get the new PO ID from the response - but the mutation doesn't return it directly
    // For now, redirect to list. In a real app, we'd get the ID from the response.
    router.push("/purchase-orders");
  }

  return (
    <div className="flex flex-col gap-4 pt-4">
      <h1 className="text-[20px] text-[var(--color-text-hi)]">New purchase order</h1>
      <PurchaseOrderForm
        defaultValues={FORM_DEFAULTS}
        submitLabel="Create purchase order"
        onSubmit={handleSubmit}
      />
    </div>
  );
}