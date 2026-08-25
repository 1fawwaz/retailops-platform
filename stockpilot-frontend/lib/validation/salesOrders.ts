import { z } from "zod";

export const salesOrderLineSchema = z.object({
  id: z.number().int(),
  sku: z.string(),
  quantity: z.number().int(),
  unit_price: z.number(),
});
export type SalesOrderLine = z.infer<typeof salesOrderLineSchema>;

export const salesOrderSchema = z.object({
  id: z.number().int(),
  customer_id: z.number().int(),
  warehouse_id: z.number().int(),
  status: z.string(),
  created_by_user_id: z.number().int().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  lines: z.array(salesOrderLineSchema),
});
export type SalesOrder = z.infer<typeof salesOrderSchema>;

export const salesOrderListResponseSchema = z.array(salesOrderSchema);

function coerceOptionalNumber(value: unknown): number | null {
  if (value === "" || value === undefined || value === null) return null;
  if (typeof value === "number") return Number.isNaN(value) ? null : value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isNaN(parsed) ? null : parsed;
  }
  return null;
}

const optionalNumber = z.preprocess(coerceOptionalNumber, z.number().nullable());
const optionalInt = z.preprocess(coerceOptionalNumber, z.number().int().nullable());

export const salesOrderLineFormSchema = z.object({
  sku: z.string().min(1, "SKU is required"),
  quantity: optionalInt.refine((val) => val === null || val > 0, "Quantity must be positive"),
  unit_price: optionalNumber.refine((val) => val === null || val >= 0, "Unit price must be non-negative"),
});

export const salesOrderFormSchema = z.object({
  customer_id: z.number().int().min(1, "Customer is required"),
  warehouse_id: z.number().int().min(1, "Warehouse is required"),
  lines: z.array(salesOrderLineFormSchema).min(1, "At least one line is required"),
});
export type SalesOrderFormValues = z.infer<typeof salesOrderFormSchema>;
export type SalesOrderLineFormValues = z.infer<typeof salesOrderLineFormSchema>;