"use client";

import { useState } from "react";
import { Form } from "../../../components/forms/Form";
import { FormField } from "../../../components/forms/FormField";
import { FormSelectField } from "../../../components/forms/FormSelectField";
import { useCategories } from "../../../hooks/useCategories";
import { useBrands } from "../../../hooks/useBrands";
import { useSuppliers } from "../../../hooks/useSuppliers";
import {
  productFormSchema,
  type ProductFormValues,
} from "../../../lib/validation/products";
import { AppError } from "../../../lib/api/errors";

export interface ProductFormProps {
  mode: "create" | "edit";
  defaultValues: ProductFormValues;
  submitLabel: string;
  onSubmit: (values: ProductFormValues) => Promise<void>;
}

export function ProductForm({ mode, defaultValues, submitLabel, onSubmit }: ProductFormProps) {
  const categories = useCategories();
  const brands = useBrands();
  const suppliers = useSuppliers();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(values: ProductFormValues) {
    setSubmitError(null);
    setSubmitting(true);
    try {
      await onSubmit(values);
    } catch (err) {
      setSubmitError(
        err instanceof AppError ? err.message : "Something went wrong. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Form
      schema={productFormSchema}
      defaultValues={defaultValues}
      onSubmit={handleSubmit}
      className="max-w-md"
    >
      {mode === "create" && <FormField<ProductFormValues> name="sku" label="SKU" />}
      <FormField<ProductFormValues> name="description" label="Description" />
      <FormSelectField<ProductFormValues>
        name="category_id"
        label="Category"
        placeholder={categories.isPending ? "Loading…" : "None"}
        options={(categories.data ?? []).map((category) => ({
          value: String(category.id),
          label: category.name,
        }))}
      />
      <FormSelectField<ProductFormValues>
        name="brand_id"
        label="Brand"
        placeholder={brands.isPending ? "Loading…" : "None"}
        options={(brands.data ?? []).map((brand) => ({
          value: String(brand.id),
          label: brand.name,
        }))}
      />
      <FormSelectField<ProductFormValues>
        name="supplier_id"
        label="Supplier"
        placeholder={suppliers.isPending ? "Loading…" : "None"}
        options={(suppliers.data ?? []).map((supplier) => ({
          value: String(supplier.id),
          label: supplier.name,
        }))}
      />
      <FormField<ProductFormValues> name="unit_cost" label="Cost price (£)" type="number" />
      <FormField<ProductFormValues> name="sale_price" label="Sale price (£)" type="number" />
      <FormField<ProductFormValues> name="reorder_point" label="Reorder point" type="number" />
      <FormField<ProductFormValues> name="safety_stock" label="Safety stock" type="number" />
      {submitError && (
        <p role="alert" className="mb-4 text-[13px] text-[var(--color-danger)]">
          {submitError}
        </p>
      )}
      <button
        type="submit"
        disabled={submitting}
        className="rounded-[6px] bg-[var(--color-accent)] px-3 py-2 text-[14px] font-medium text-[var(--color-canvas)] transition-colors duration-150 disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-accent)]"
      >
        {submitting ? "Saving…" : submitLabel}
      </button>
    </Form>
  );
}
