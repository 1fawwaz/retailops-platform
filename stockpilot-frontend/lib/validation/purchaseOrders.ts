import { z } from "zod";

const provenanceMap = z.record(z.string(), z.string());

export const purchaseOrderLineSchema = z.object({
  id: z.number().int(),
  sku: z.string(),
  quantity_ordered: z.number().int(),
  quantity_received: z.number().int(),
  unit_cost: z.number().nullable(),
  _provenance: provenanceMap.optional(),
  _derivation_ref: provenanceMap.optional(),
});

export const purchaseOrderSchema = z.object({
  id: z.number().int(),
  supplier_id: z.number().int(),
  warehouse_id: z.number().int(),
  status: z.string(),
  created_by_user_id: z.number().int().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  lines: z.array(purchaseOrderLineSchema),
  _provenance: provenanceMap.optional(),
  _derivation_ref: provenanceMap.optional(),
});
export type PurchaseOrder = z.infer<typeof purchaseOrderSchema>;
export const purchaseOrderListResponseSchema = z.array(purchaseOrderSchema);

function coerceOptionalNumber(value: unknown): number | null {
  if (value === "" || value === undefined || value === null) return null;
  if (typeof value === "number") return Number.isNaN(value) ? null : value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isNaN(parsed) ? null : parsed;
  }
  return null;
}

const optionalId = z.preprocess(coerceOptionalNumber, z.number().int().nullable());
const optionalAmount = z.preprocess(coerceOptionalNumber, z.number().nullable());

export const purchaseOrderLineCreateSchema = z.object({
  sku: z.string().min(1, "SKU is required"),
  quantity_ordered: z.number().int().positive("Quantity must be positive"),
  unit_cost: optionalAmount,
});
export type PurchaseOrderLineCreate = z.infer<typeof purchaseOrderLineCreateSchema>;

export const purchaseOrderCreateSchema = z.object({
  supplier_id: z.number().int().positive("Supplier is required"),
  warehouse_id: z.number().int().positive("Warehouse is required"),
  lines: z.array(purchaseOrderLineCreateSchema).min(1, "At least one line is required"),
});
export type PurchaseOrderCreate = z.infer<typeof purchaseOrderCreateSchema>;

export const purchaseOrderLineUpdateSchema = z.object({
  id: z.number().int().optional(),
  sku: z.string().min(1, "SKU is required"),
  quantity_ordered: z.number().int().positive("Quantity must be positive"),
  unit_cost: optionalAmount,
});

export const purchaseOrderUpdateSchema = z.object({
  supplier_id: optionalId,
  warehouse_id: optionalId,
  lines: z.array(purchaseOrderLineUpdateSchema).min(1, "At least one line is required").optional(),
});
export type PurchaseOrderUpdate = z.infer<typeof purchaseOrderUpdateSchema>;

export const receiveLineSchema = z.object({
  line_id: z.number().int().positive(),
  quantity: z.number().int().positive("Quantity must be positive"),
  over_receipt_confirmed: z.boolean().default(false),
});

export const receiveRequestSchema = z.object({
  lines: z.array(receiveLineSchema).min(1, "At least one line is required"),
});
export type ReceiveRequest = z.infer<typeof receiveRequestSchema>;

export const purchaseOrderFormSchema = z.object({
  supplier_id: z.number().int().positive("Supplier is required"),
  warehouse_id: z.number().int().positive("Warehouse is required"),
  lines: z.array(purchaseOrderLineCreateSchema).min(1, "At least one line is required"),
});
export type PurchaseOrderFormValues = z.infer<typeof purchaseOrderFormSchema>;

export const receiveFormLineSchema = z.object({
  line_id: z.number().int().positive(),
  quantity: z.number().int().positive("Quantity must be positive"),
  over_receipt_confirmed: z.boolean().default(false),
});

export const receiveFormSchema = z.object({
  lines: z.array(receiveFormLineSchema).min(1, "At least one line is required"),
});
export type ReceiveFormValues = z.infer<typeof receiveFormSchema>;