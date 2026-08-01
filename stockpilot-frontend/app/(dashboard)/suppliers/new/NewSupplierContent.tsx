"use client";

import { useRouter } from "next/navigation";
import { SupplierForm } from "../SupplierForm";
import { useCreateSupplier } from "../../../../hooks/useCreateSupplier";
import { useCan } from "../../../../lib/rbac";
import { EmptyState } from "../../../../components/ui/EmptyState";
import type { SupplierFormValues } from "../../../../lib/validation/suppliers";

const EMPTY_DEFAULTS: SupplierFormValues = {
  name: "",
  lead_time_days: 0,
  reliability_score: 1,
};

export function NewSupplierContent() {
  const router = useRouter();
  const canCreate = useCan("suppliers:create");
  const createSupplier = useCreateSupplier();

  if (!canCreate) {
    return (
      <EmptyState
        title="You don't have permission to create suppliers"
        description="Ask an administrator to grant you the suppliers:create permission."
      />
    );
  }

  async function handleSubmit(values: SupplierFormValues) {
    const supplier = await createSupplier.mutateAsync(values);
    router.push(`/suppliers/${supplier.id}`);
  }

  return (
    <div className="flex flex-col gap-4 pt-4">
      <h1 className="text-[20px] text-[var(--color-text-hi)]">New supplier</h1>
      <SupplierForm defaultValues={EMPTY_DEFAULTS} submitLabel="Create supplier" onSubmit={handleSubmit} />
    </div>
  );
}
