"use client";

import { useRouter } from "next/navigation";
import { ProductForm } from "../ProductForm";
import { useCreateProduct } from "../../../../hooks/useCreateProduct";
import { useCan } from "../../../../lib/rbac";
import { EmptyState } from "../../../../components/ui/EmptyState";
import type { ProductFormValues } from "../../../../lib/validation/products";

const EMPTY_DEFAULTS: ProductFormValues = {
  sku: "",
  description: "",
  category_id: null,
  supplier_id: null,
  brand_id: null,
  unit_cost: null,
  sale_price: null,
  reorder_point: null,
  safety_stock: null,
};

export function NewProductContent() {
  const router = useRouter();
  const canCreate = useCan("products:create");
  const createProduct = useCreateProduct();

  if (!canCreate) {
    return (
      <EmptyState
        title="You don't have permission to create products"
        description="Ask an administrator to grant you the products:create permission."
      />
    );
  }

  async function handleSubmit(values: ProductFormValues) {
    const product = await createProduct.mutateAsync(values);
    router.push(`/products/${encodeURIComponent(product.sku)}`);
  }

  return (
    <div className="flex flex-col gap-4 pt-4">
      <h1 className="text-[20px] text-[var(--color-text-hi)]">New product</h1>
      <ProductForm
        mode="create"
        defaultValues={EMPTY_DEFAULTS}
        submitLabel="Create product"
        onSubmit={handleSubmit}
      />
    </div>
  );
}
