"use client";

import { useRouter } from "next/navigation";
import { SalesOrderForm } from "../SalesOrderForm";
import { useSalesOrder, useUpdateSalesOrder } from "../../../../../hooks/useSalesOrders";
import { useCan } from "../../../../../lib/rbac";
import { EmptyState } from "../../../../../components/ui/EmptyState";
import { AppError } from "../../../../../lib/api/errors";
import type { SalesOrderFormValues } from "../../../../../lib/validation/salesOrders";

export function EditSalesOrderContent({ id }: { id: number }) {
  const router = useRouter();
  const canUpdate = useCan("sales:update");
  const order = useSalesOrder(id);
  const updateSalesOrder = useUpdateSalesOrder();

  if (!canUpdate) {
    return (
      <EmptyState
        title="You don't have permission to edit sales orders"
        description="Ask an administrator to grant you the sales:update permission."
      />
    );
  }

  if (order.isPending) {
    return (
      <div className="flex flex-col gap-3 pt-4" aria-busy="true">
        <div className="h-6 w-48 animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
      </div>
    );
  }

  if (order.isError) {
    return (
      <p className="pt-4 text-[13px] text-[var(--color-danger)]">
        {order.error instanceof AppError ? order.error.message : "Could not load this order."}
      </p>
    );
  }

  if (!order.data) {
    return <EmptyState title="Order not found" description={`No order exists with ID ${id}.`} />;
  }

  // Only draft orders can be edited
  if (order.data.status !== "draft") {
    return (
      <EmptyState
        title="Cannot edit this order"
        description="Only draft orders can be edited."
      />
    );
  }

  async function handleSubmit(values: SalesOrderFormValues) {
    await updateSalesOrder.mutateAsync({ id, values });
    router.push(`/sales/orders/${id}`);
  }

  return (
    <div className="flex flex-col gap-4 pt-4">
      <h1 className="text-[20px] text-[var(--color-text-hi)]">Edit sales order</h1>
      <SalesOrderForm
        mode="edit"
        defaultValues={order.data}
        submitLabel="Save changes"
        onSubmit={handleSubmit}
      />
    </div>
  );
}