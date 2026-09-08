"use client";

import { useState } from "react";
import { Form } from "../../../../components/forms/Form";
import { FormField } from "../../../../components/forms/FormField";
import {
  customerFormSchema,
  type CustomerFormValues,
} from "../../../../lib/validation/customers";
import { AppError } from "../../../../lib/api/errors";

export interface CustomerFormProps {
  mode: "create" | "edit";
  defaultValues: CustomerFormValues;
  submitLabel: string;
  onSubmit: (values: CustomerFormValues) => Promise<void>;
}

export function CustomerForm({ defaultValues, submitLabel, onSubmit }: CustomerFormProps) {
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(values: CustomerFormValues) {
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
      schema={customerFormSchema}
      defaultValues={defaultValues}
      onSubmit={handleSubmit}
      className="max-w-md"
    >
      <FormField<CustomerFormValues> name="name" label="Name" />
      <FormField<CustomerFormValues> name="email" label="Email" type="email" />
      <FormField<CustomerFormValues> name="phone" label="Phone" type="text" />
      <FormField<CustomerFormValues> name="country" label="Country" />
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