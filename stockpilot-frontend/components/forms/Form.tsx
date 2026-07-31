"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import {
  FormProvider,
  useForm,
  type FieldValues,
  type DefaultValues,
  type Resolver,
} from "react-hook-form";
import type { z } from "zod";

// docs/CLAUDE.md §6: "a new resource's form is built by passing
// column/field config into the shared primitive." A resource's form
// supplies its own zod schema (already the app's one validation source
// per CLAUDE.md §4 -- z.infer, never a hand-duplicated type) and gets
// react-hook-form wiring, submit/error state, and the AppError ->
// field-message mapping (docs/ARCHITECTURE.md § Error Handling
// Architecture) for free via FormField below.
//
// Generic over TFieldValues (not the schema type) deliberately -- Zod
// 4's ZodType<Output, Input> generics don't infer cleanly through a
// second level of generic indirection (schema -> z.infer<schema> in the
// same parameter list); asking the caller to state TFieldValues once
// (as FormField already requires) and typing `schema` against it
// directly avoids that inference dead end.

export interface FormProps<TFieldValues extends FieldValues> {
  schema: z.ZodType<TFieldValues>;
  defaultValues: DefaultValues<TFieldValues>;
  onSubmit: (values: TFieldValues) => Promise<void> | void;
  children: React.ReactNode;
  className?: string;
}

export function Form<TFieldValues extends FieldValues>({
  schema,
  defaultValues,
  onSubmit,
  children,
  className,
}: FormProps<TFieldValues>) {
  // zodResolver's overloads can't be resolved against a *generic,
  // constrained* TFieldValues (as opposed to a concrete field-values
  // type) -- a documented friction point between @hookform/resolvers'
  // Zod-4-oriented overloads and generic wrapper components, not a real
  // type hole: `schema` is already declared as `z.ZodType<TFieldValues>`
  // in FormProps above; pinning its input type here too (our forms don't
  // use zod .transform(), so input and output are the same shape) is
  // what the overload needs to resolve at all.
  const resolver = zodResolver(schema as z.ZodType<TFieldValues, TFieldValues>) as Resolver<
    TFieldValues
  >;
  const methods = useForm<TFieldValues>({
    resolver,
    defaultValues,
  });

  return (
    <FormProvider {...methods}>
      <form
        className={className}
        noValidate
        onSubmit={methods.handleSubmit(async (values) => {
          await onSubmit(values);
        })}
      >
        {children}
      </form>
    </FormProvider>
  );
}
