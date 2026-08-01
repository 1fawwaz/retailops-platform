"use client";

import { useFormContext, type FieldValues, type Path } from "react-hook-form";

// Same label/error/aria contract as FormField.tsx, for the <select>
// case FormField doesn't cover (docs/CLAUDE.md §6: shared, config-driven
// primitives, not a one-off select per page).

export interface FormSelectFieldOption {
  value: string;
  label: string;
}

export interface FormSelectFieldProps<TFieldValues extends FieldValues> {
  name: Path<TFieldValues>;
  label: string;
  options: FormSelectFieldOption[];
  /** Rendered as the first, disabled-to-select-again option -- e.g. "None". */
  placeholder?: string;
}

export function FormSelectField<TFieldValues extends FieldValues>({
  name,
  label,
  options,
  placeholder,
}: FormSelectFieldProps<TFieldValues>) {
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
      <select
        id={inputId}
        aria-invalid={errorMessage ? true : undefined}
        aria-describedby={errorMessage ? errorId : undefined}
        className={`w-full rounded-[6px] border bg-[var(--color-canvas)] px-3 py-2 text-[14px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)] ${
          errorMessage ? "border-[var(--color-danger)]" : "border-[var(--color-hairline)]"
        }`}
        {...register(name)}
      >
        {placeholder && <option value="">{placeholder}</option>}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {errorMessage && (
        <p id={errorId} role="alert" className="mt-1 text-[13px] text-[var(--color-danger)]">
          {errorMessage}
        </p>
      )}
    </div>
  );
}
