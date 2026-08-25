import { z } from "zod";

export const customerSchema = z.object({
  id: z.number().int(),
  name: z.string(),
  email: z.string().nullable(),
  phone: z.string().nullable(),
  country: z.string().nullable(),
  created_at: z.string(),
});
export type Customer = z.infer<typeof customerSchema>;

export const customerListResponseSchema = z.array(customerSchema);

function coerceOptionalString(value: unknown): string | null {
  if (value === "" || value === undefined || value === null) return null;
  if (typeof value === "string") return value;
  return String(value);
}

const optionalString = z.preprocess(coerceOptionalString, z.string().nullable());

export const customerFormSchema = z.object({
  name: z.string().min(1, "Name is required"),
  email: optionalString,
  phone: optionalString,
  country: optionalString,
});
export type CustomerFormValues = z.infer<typeof customerFormSchema>;