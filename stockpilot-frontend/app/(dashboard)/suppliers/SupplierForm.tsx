"use client";

import { useState } from "react";
import { Form } from "../../../components/forms/Form";
import { FormField } from "../../../components/forms/FormField";
import { supplierFormSchema, type SupplierFormValues } from "../../../lib/validation/suppliers";
import { AppError } from "../../../lib/api/errors";

export interface SupplierFormProps {
  defaultValues: SupplierFormValues;
  submitLabel: string;
  onSubmit: (values: SupplierFormValues) => Promise<void>;
}

export function SupplierForm({ defaultValues, submitLabel, onSubmit }: SupplierFormProps) {
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(values: SupplierFormValues) {
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
      schema={supplierFormSchema}
      defaultValues={defaultValues}
      onSubmit={handleSubmit}
      className="max-w-md"
    >
      <FormField<SupplierFormValues> name="name" label="Name" />
      <FormField<SupplierFormValues> name="lead_time_days" label="Lead time (days)" type="number" />
      <FormField<SupplierFormValues>
        name="reliability_score"
        label="Reliability score (0-1)"
        type="number"
      />
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
