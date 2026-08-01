"use client";

import { useRouter } from "next/navigation";
import { ProductForm } from "../../ProductForm";
import { useProduct } from "../../../../../hooks/useProduct";
import { useUpdateProduct } from "../../../../../hooks/useUpdateProduct";
import { useCategories } from "../../../../../hooks/useCategories";
import { useBrands } from "../../../../../hooks/useBrands";
import { useSuppliers } from "../../../../../hooks/useSuppliers";
import { useCan } from "../../../../../lib/rbac";
import { EmptyState } from "../../../../../components/ui/EmptyState";
import { AppError } from "../../../../../lib/api/errors";
import type { ProductFormValues } from "../../../../../lib/validation/products";

export function EditProductContent({ sku }: { sku: string }) {
  const router = useRouter();
  const product = useProduct(sku);
  const canUpdate = useCan("products:update");
  const updateProduct = useUpdateProduct(sku);
  // ProductForm's category/brand/supplier <select> options load
  // asynchronously; react-hook-form seeds a native <select>'s DOM value
  // from defaultValues at mount, before any <option> exists yet if these
  // are still loading, and a browser <select> does NOT retroactively
  // re-select once options later appear -- it silently stays on the
  // first option ("None"), which would submit a false null and blank out
  // a real category/brand/supplier on save. Blocking the form's mount
  // until all three have resolved avoids the race entirely.
  const categories = useCategories();
  const brands = useBrands();
  const suppliers = useSuppliers();

  if (!canUpdate) {
    return (
      <EmptyState
        title="You don't have permission to edit products"
        description="Ask an administrator to grant you the products:update permission."
      />
    );
  }

  if (product.isPending || categories.isPending || brands.isPending || suppliers.isPending) {
    return (
      <div className="flex flex-col gap-3 pt-4" aria-busy="true">
        <div className="h-6 w-48 animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
        <div className="h-64 w-full max-w-md animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
      </div>
    );
  }

  if (product.isError) {
    if (product.error instanceof AppError && product.error.status === 404) {
      return <EmptyState title="Product not found" description={`No product exists with SKU ${sku}.`} />;
    }
    return (
      <p className="pt-4 text-[13px] text-[var(--color-danger)]">
        {product.error instanceof AppError ? product.error.message : "Could not load this product."}
      </p>
    );
  }

  if (!product.data) {
    return <EmptyState title="Product not found" description={`No product exists with SKU ${sku}.`} />;
  }

  if (categories.isError || brands.isError || suppliers.isError) {
    return (
      <p className="pt-4 text-[13px] text-[var(--color-danger)]">
        Could not load categories, brands, or suppliers. Please try again.
      </p>
    );
  }

  const defaultValues: ProductFormValues = {
    sku: product.data.sku,
    description: product.data.description ?? "",
    category_id: product.data.category_id,
    supplier_id: product.data.supplier_id,
    brand_id: product.data.brand_id,
    unit_cost: product.data.unit_cost,
    sale_price: product.data.sale_price,
    reorder_point: product.data.reorder_point,
    safety_stock: product.data.safety_stock,
  };

  async function handleSubmit(values: ProductFormValues) {
    // PUT /products/{sku} has no sku field in its body (see
    // lib/api/products.ts's updateProduct) -- stripped here, not just
    // retyped, so it's never actually sent.
    await updateProduct.mutateAsync({
      description: values.description,
      category_id: values.category_id,
      supplier_id: values.supplier_id,
      brand_id: values.brand_id,
      unit_cost: values.unit_cost,
      sale_price: values.sale_price,
      reorder_point: values.reorder_point,
      safety_stock: values.safety_stock,
    });
    router.push(`/products/${encodeURIComponent(sku)}`);
  }

  return (
    <div className="flex flex-col gap-4 pt-4">
      <h1 className="text-[20px] text-[var(--color-text-hi)]">Edit {sku}</h1>
      <ProductForm
        mode="edit"
        defaultValues={defaultValues}
        submitLabel="Save changes"
        onSubmit={handleSubmit}
      />
    </div>
  );
}
