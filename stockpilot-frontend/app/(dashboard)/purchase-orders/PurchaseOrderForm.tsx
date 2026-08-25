"use client";

import { useState } from "react";
import { Form } from "../../../components/forms/Form";
import { FormSelectField } from "../../../components/forms/FormSelectField";
import { useProducts } from "../../../hooks/useProducts";
import { useSuppliers } from "../../../hooks/useSuppliers";
import { useWarehouses } from "../../../hooks/useWarehouses";
import {
  type PurchaseOrderFormValues,
  type PurchaseOrderLineCreate,
} from "../../../lib/validation/purchaseOrders";
import { AppError } from "../../../lib/api/errors";
import { z } from "zod";

const LINE_DEFAULTS: PurchaseOrderLineCreate = { sku: "", quantity_ordered: 1, unit_cost: null };

// Schema for the main form fields (supplier, warehouse) - lines handled separately
const purchaseOrderMainSchema = z.object({
  supplier_id: z.number().int().positive("Supplier is required"),
  warehouse_id: z.number().int().positive("Warehouse is required"),
});

type PurchaseOrderMainSchema = z.infer<typeof purchaseOrderMainSchema>;

export function PurchaseOrderForm({
  defaultValues,
  submitLabel,
  onSubmit,
}: {
  defaultValues: PurchaseOrderFormValues;
  submitLabel: string;
  onSubmit: (values: PurchaseOrderFormValues) => Promise<void>;
}) {
  const products = useProducts({ limit: 1000 });
  const suppliers = useSuppliers();
  const warehouses = useWarehouses();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [lines, setLines] = useState<PurchaseOrderLineCreate[]>(defaultValues.lines.length > 0 ? defaultValues.lines : [LINE_DEFAULTS]);

  async function handleSubmit(values: PurchaseOrderMainSchema) {
    setSubmitError(null);
    setSubmitting(true);
    try {
      await onSubmit({ ...values, lines });
    } catch (err) {
      setSubmitError(
        err instanceof AppError ? err.message : "Something went wrong. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  function updateLine(index: number, field: keyof PurchaseOrderLineCreate, value: string | number | null) {
    const newLines = [...lines];
    newLines[index] = { ...newLines[index], [field]: value as PurchaseOrderLineCreate[keyof PurchaseOrderLineCreate] };
    setLines(newLines);
  }

  function addLine() {
    setLines([...lines, LINE_DEFAULTS]);
  }

  function removeLine(index: number) {
    if (lines.length <= 1) return;
    setLines(lines.filter((_, i) => i !== index));
  }

  return (
    <Form
      schema={purchaseOrderMainSchema}
      defaultValues={{
        supplier_id: defaultValues.supplier_id,
        warehouse_id: defaultValues.warehouse_id,
      }}
      onSubmit={handleSubmit}
      className="max-w-3xl"
    >
      <div className="mb-4">
        <FormSelectField<PurchaseOrderFormValues>
          name="supplier_id"
          label="Supplier"
          placeholder={suppliers.isPending ? "Loading…" : "Select supplier"}
          options={(suppliers.data ?? []).map((supplier) => ({
            value: String(supplier.id),
            label: supplier.name,
          }))}
        />
      </div>

      <div className="mb-4">
        <FormSelectField<PurchaseOrderFormValues>
          name="warehouse_id"
          label="Warehouse"
          placeholder={warehouses.isPending ? "Loading…" : "Select warehouse"}
          options={(warehouses.data ?? []).map((warehouse) => ({
            value: String(warehouse.id),
            label: warehouse.name,
          }))}
        />
      </div>

      <div className="mb-4">
        <h3 className="mb-2 text-[14px] font-medium text-[var(--color-text-hi)]">Lines</h3>
        {lines.map((line, index) => (
          <div key={index} className="flex flex-col sm:flex-row gap-2 mb-2 p-3 rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)]">
            <div className="flex-1 min-w-[200px]">
              <label className="mb-1 block text-[12px] text-[var(--color-text-mid)]">SKU</label>
              <select
                value={line.sku}
                onChange={(e) => updateLine(index, "sku", e.target.value)}
                className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-canvas)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
              >
                <option value="">Select product</option>
                {(products.data ?? []).map((product) => (
                  <option key={product.sku} value={product.sku}>
                    {product.sku} — {product.description ?? "No description"}
                  </option>
                ))}
              </select>
            </div>
            <div className="w-32">
              <label className="mb-1 block text-[12px] text-[var(--color-text-mid)]">Qty ordered</label>
              <input
                type="number"
                min="1"
                value={line.quantity_ordered}
                onChange={(e) => updateLine(index, "quantity_ordered", Number(e.target.value) || 1)}
                className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-canvas)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
              />
            </div>
            <div className="w-40">
              <label className="mb-1 block text-[12px] text-[var(--color-text-mid)]">Unit cost (₹)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={line.unit_cost ?? ""}
                onChange={(e) => updateLine(index, "unit_cost", e.target.value ? Number(e.target.value) : null)}
                className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-canvas)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
              />
            </div>
            <div className="flex items-end">
              <button
                type="button"
                onClick={() => removeLine(index)}
                disabled={lines.length <= 1}
                className="h-10 rounded-[6px] border border-[var(--color-danger)] px-2 text-[12px] text-[var(--color-danger)] hover:bg-[var(--color-danger)] hover:text-[var(--color-canvas)] disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
              >
                Remove
              </button>
            </div>
          </div>
        ))}
        <button
          type="button"
          onClick={addLine}
          className="rounded-[6px] border border-[var(--color-hairline)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] transition-colors duration-150 hover:border-[var(--color-hairline-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
        >
          Add line
        </button>
      </div>

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