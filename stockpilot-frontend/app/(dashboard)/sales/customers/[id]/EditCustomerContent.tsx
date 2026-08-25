"use client";

import { useRouter } from "next/navigation";
import { CustomerForm } from "../CustomerForm";
import { useCustomer, useUpdateCustomer } from "../../../../../hooks/useCustomers";
import { useCan } from "../../../../../lib/rbac";
import { EmptyState } from "../../../../../components/ui/EmptyState";
import { AppError } from "../../../../../lib/api/errors";
import type { CustomerFormValues } from "../../../../../lib/validation/customers";

export function EditCustomerContent({ id }: { id: number }) {
  const router = useRouter();
  const canUpdate = useCan("customers:update");
  const customer = useCustomer(id);
  const updateCustomer = useUpdateCustomer();

  if (!canUpdate) {
    return (
      <EmptyState
        title="You don't have permission to edit customers"
        description="Ask an administrator to grant you the customers:update permission."
      />
    );
  }

  if (customer.isPending) {
    return (
      <div className="flex flex-col gap-3 pt-4" aria-busy="true">
        <div className="h-6 w-48 animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
      </div>
    );
  }

  if (customer.isError) {
    return (
      <p className="pt-4 text-[13px] text-[var(--color-danger)]">
        {customer.error instanceof AppError ? customer.error.message : "Could not load this customer."}
      </p>
    );
  }

  if (!customer.data) {
    return <EmptyState title="Customer not found" description={`No customer exists with ID ${id}.`} />;
  }

  async function handleSubmit(values: CustomerFormValues) {
    await updateCustomer.mutateAsync({ id, values });
    router.push(`/sales/customers/${id}`);
  }

  return (
    <div className="flex flex-col gap-4 pt-4">
      <h1 className="text-[20px] text-[var(--color-text-hi)]">Edit customer</h1>
      <CustomerForm
        mode="edit"
        defaultValues={customer.data}
        submitLabel="Save changes"
        onSubmit={handleSubmit}
      />
    </div>
  );
}