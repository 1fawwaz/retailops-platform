"use client";

import { useState } from "react";
import { Form } from "../../../../components/forms/Form";
import { FormField } from "../../../../components/forms/FormField";
import { FormSelectField } from "../../../../components/forms/FormSelectField";
import { useCustomers } from "../../../../hooks/useCustomers";
import { useWarehouses } from "../../../../hooks/useWarehouses";
import { useProducts } from "../../../../hooks/useProducts";
import {
  salesOrderFormSchema,
  type SalesOrderFormValues,
} from "../../../../lib/validation/salesOrders";
import { AppError } from "../../../../lib/api/errors";

export interface SalesOrderFormProps {
  mode: "create" | "edit";
  defaultValues: SalesOrderFormValues;
  submitLabel: string;
  onSubmit: (values: SalesOrderFormValues) => Promise<void>;
}

export function SalesOrderForm({ mode, defaultValues, submitLabel, onSubmit }: SalesOrderFormProps) {
  const customers = useCustomers({ limit: 1000, offset: 0 });
  const warehouses = useWarehouses();
  const products = useProducts({ limit: 1000, offset: 0 });
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(values: SalesOrderFormValues) {
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
      schema={salesOrderFormSchema}
      defaultValues={defaultValues}
      onSubmit={handleSubmit}
      className="max-w-2xl"
    >
      <FormSelectField<SalesOrderFormValues>
        name="customer_id"
        label="Customer"
        placeholder={customers.isPending ? "Loading…" : "Select a customer"}
        options={(customers.data ?? []).map((customer) => ({
          value: String(customer.id),
          label: `${customer.name} (${customer.email ?? "no email"})`,
        }))}
      />
      <FormSelectField<SalesOrderFormValues>
        name="warehouse_id"
        label="Warehouse"
        placeholder={warehouses.isPending ? "Loading…" : "Select a warehouse"}
        options={(warehouses.data ?? []).map((warehouse) => ({
          value: String(warehouse.id),
          label: warehouse.name,
        }))}
      />
      <div className="border-t border-[var(--color-hairline)] pt-4 mt-4">
        <h3 className="mb-3 text-[14px] font-medium text-[var(--color-text-hi)]">Order Lines</h3>
        <p className="text-[13px] text-[var(--color-text-mid)] mb-4">
          Line editing requires the useFieldArray hook which is not yet configured.
          Please use the API directly for multi-line orders.
        </p>
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