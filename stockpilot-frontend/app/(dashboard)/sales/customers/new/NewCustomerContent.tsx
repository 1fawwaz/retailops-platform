"use client";

import { useRouter } from "next/navigation";
import { CustomerForm } from "../CustomerForm";
import { useCreateCustomer } from "../../../../../hooks/useCustomers";
import { useCan } from "../../../../../lib/rbac";
import { EmptyState } from "../../../../../components/ui/EmptyState";
import type { CustomerFormValues } from "../../../../../lib/validation/customers";

const EMPTY_DEFAULTS: CustomerFormValues = {
  name: "",
  email: null,
  phone: null,
  country: null,
};

export function NewCustomerContent() {
  const router = useRouter();
  const canCreate = useCan("customers:create");
  const createCustomer = useCreateCustomer();

  if (!canCreate) {
    return (
      <EmptyState
        title="You don't have permission to create customers"
        description="Ask an administrator to grant you the customers:create permission."
      />
    );
  }

  async function handleSubmit(values: CustomerFormValues) {
    const customer = await createCustomer.mutateAsync(values);
    router.push(`/sales/customers/${customer.id}`);
  }

  return (
    <div className="flex flex-col gap-4 pt-4">
      <h1 className="text-[20px] text-[var(--color-text-hi)]">New customer</h1>
      <CustomerForm
        mode="create"
        defaultValues={EMPTY_DEFAULTS}
        submitLabel="Create customer"
        onSubmit={handleSubmit}
      />
    </div>
  );
}