import { z } from "zod";

const provenanceMap = z.record(z.string(), z.string());

// Mirrors contracts/stockpilot-api/schemas/list_products_route_products_get.json
// exactly (Backend Module 2: brand_id/sale_price/history now exist).
export const productSchema = z.object({
  _provenance: provenanceMap,
  _derivation_ref: provenanceMap,
  sku: z.string(),
  description: z.string().nullable(),
  category_id: z.number().int().nullable(),
  supplier_id: z.number().int().nullable(),
  brand_id: z.number().int().nullable(),
  unit_cost: z.number().nullable(),
  sale_price: z.number().nullable(),
  reorder_point: z.number().int().nullable(),
  safety_stock: z.number().int().nullable(),
  image_url: z.string().nullable().optional(),
  created_at: z.string(),
});
export type Product = z.infer<typeof productSchema>;

export const productListResponseSchema = z.array(productSchema);

// Mirrors get_product_route_products__sku__get.json's ProductDetail exactly.
export const movementHistoryEntrySchema = z.object({
  movement_date: z.string(),
  quantity_delta: z.number().int(),
  movement_type: z.string(),
  provenance: z.string(),
});
export type MovementHistoryEntry = z.infer<typeof movementHistoryEntrySchema>;

export const productDetailSchema = productSchema.extend({
  quantity_on_hand: z.number().int().nullable(),
  movement_history: z.array(movementHistoryEntrySchema),
});
export type ProductDetail = z.infer<typeof productDetailSchema>;

// Mirrors get_product_history_route_products__sku__history_get.json exactly.
export const productHistoryEntrySchema = z.object({
  field_name: z.string(),
  old_value: z.string().nullable(),
  new_value: z.string().nullable(),
  changed_by_user_id: z.number().int().nullable(),
  changed_at: z.string(),
});
export type ProductHistoryEntry = z.infer<typeof productHistoryEntrySchema>;
export const productHistoryResponseSchema = z.array(productHistoryEntrySchema);

// Mirrors create_product_route_products_post.json's ProductCreate exactly.
// A number <input> (FormField, valueAsNumber) produces number | NaN for
// an empty field; a native <select> (FormSelectField) always produces a
// string, empty string included -- this form mixes both for its
// optional numeric fields, so the coercion has to accept either shape,
// not assume one.
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

export const productFormSchema = z.object({
  sku: z.string().min(1, "SKU is required"),
  description: z.string().optional(),
  category_id: optionalId,
  supplier_id: optionalId,
  brand_id: optionalId,
  unit_cost: optionalAmount,
  sale_price: optionalAmount,
  reorder_point: optionalId,
  safety_stock: optionalId,
  image_url: z.string().nullable().optional(),
});
export type ProductFormValues = z.infer<typeof productFormSchema>;

