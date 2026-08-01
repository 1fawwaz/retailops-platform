"use client";

import { useRouter } from "next/navigation";
import { SupplierForm } from "../../SupplierForm";
import { useSupplier } from "../../../../../hooks/useSupplier";
import { useUpdateSupplier } from "../../../../../hooks/useUpdateSupplier";
import { useCan } from "../../../../../lib/rbac";
import { EmptyState } from "../../../../../components/ui/EmptyState";
import { AppError } from "../../../../../lib/api/errors";
import type { SupplierFormValues } from "../../../../../lib/validation/suppliers";

export function EditSupplierContent({ supplierId }: { supplierId: number }) {
  const router = useRouter();
  const supplier = useSupplier(supplierId);
  const canUpdate = useCan("suppliers:update");
  const updateSupplier = useUpdateSupplier(supplierId);

  if (!canUpdate) {
    return (
      <EmptyState
        title="You don't have permission to edit suppliers"
        description="Ask an administrator to grant you the suppliers:update permission."
      />
    );
  }

  if (supplier.isPending) {
    return (
      <div className="flex flex-col gap-3 pt-4" aria-busy="true">
        <div className="h-6 w-48 animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
        <div className="h-64 w-full max-w-md animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
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

  const defaultValues: SupplierFormValues = {
    name: supplier.data.name,
    lead_time_days: supplier.data.lead_time_days,
    reliability_score: supplier.data.reliability_score,
  };

  async function handleSubmit(values: SupplierFormValues) {
    await updateSupplier.mutateAsync(values);
    router.push(`/suppliers/${supplierId}`);
  }

  return (
    <div className="flex flex-col gap-4 pt-4">
      <h1 className="text-[20px] text-[var(--color-text-hi)]">Edit {supplier.data.name}</h1>
      <SupplierForm defaultValues={defaultValues} submitLabel="Save changes" onSubmit={handleSubmit} />
    </div>
  );
}
