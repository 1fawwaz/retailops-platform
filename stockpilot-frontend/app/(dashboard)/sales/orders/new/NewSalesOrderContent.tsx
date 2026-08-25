"use client";

import { useRouter } from "next/navigation";
import { SalesOrderForm } from "../SalesOrderForm";
import { useCreateSalesOrder } from "../../../../../hooks/useSalesOrders";
import { useCan } from "../../../../../lib/rbac";
import { EmptyState } from "../../../../../components/ui/EmptyState";
import type { SalesOrderFormValues } from "../../../../../lib/validation/salesOrders";

const EMPTY_DEFAULTS: SalesOrderFormValues = {
  customer_id: 0,
  warehouse_id: 0,
  lines: [{ sku: "", quantity: 1, unit_price: 0 }],
};

export function NewSalesOrderContent() {
  const router = useRouter();
  const canCreate = useCan("sales:create");
  const createSalesOrder = useCreateSalesOrder();

  if (!canCreate) {
    return (
      <EmptyState
        title="You don't have permission to create sales orders"
        description="Ask an administrator to grant you the sales:create permission."
      />
    );
  }

  async function handleSubmit(values: SalesOrderFormValues) {
    const order = await createSalesOrder.mutateAsync(values);
    router.push(`/sales/orders/${order.id}`);
  }

  return (
    <div className="flex flex-col gap-4 pt-4">
      <h1 className="text-[20px] text-[var(--color-text-hi)]">New sales order</h1>
      <SalesOrderForm
        mode="create"
        defaultValues={EMPTY_DEFAULTS}
        submitLabel="Create sales order"
        onSubmit={handleSubmit}
      />
    </div>
  );
}