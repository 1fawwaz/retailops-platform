"use client";

import { useFormContext, type FieldValues, type Path } from "react-hook-form";

// docs/CLAUDE.md §11: "label every field, associate errors with their
// field via aria-describedby, announce validation errors on submit,
// don't rely on color alone for invalid-state (border + icon + text)."
// One field = one label + one input + one error message, wired the same
// way for every resource's form -- not re-implemented per page.

export interface FormFieldProps<TFieldValues extends FieldValues> {
  name: Path<TFieldValues>;
  label: string;
  type?: "text" | "email" | "password" | "number";
}

export function FormField<TFieldValues extends FieldValues>({
  name,
  label,
  type = "text",
}: FormFieldProps<TFieldValues>) {
  const {
    register,
    formState: { errors },
  } = useFormContext<TFieldValues>();

  const error = errors[name];
  const errorMessage = typeof error?.message === "string" ? error.message : undefined;
  const inputId = `field-${name}`;
  const errorId = `${inputId}-error`;

  return (
    <div className="mb-4">
      <label htmlFor={inputId} className="mb-1 block text-[13px] text-[var(--color-text-mid)]">
        {label}
      </label>
      <input
        id={inputId}
        type={type}
        aria-invalid={errorMessage ? true : undefined}
        aria-describedby={errorMessage ? errorId : undefined}
        className={`w-full rounded-[6px] border bg-[var(--color-canvas)] px-3 py-2 text-[14px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)] ${
          errorMessage ? "border-[var(--color-danger)]" : "border-[var(--color-hairline)]"
        }`}
        {...register(name, { valueAsNumber: type === "number" })}
      />
      {errorMessage && (
        <p id={errorId} role="alert" className="mt-1 text-[13px] text-[var(--color-danger)]">
          {errorMessage}
        </p>
      )}
    </div>
  );
}
