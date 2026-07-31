import { z } from "zod";

const provenanceMap = z.record(z.string(), z.string());

// Mirrors contracts/stockpilot-api/schemas/list_products_route_products_get.json
// / get_product_route_products__sku__get.json exactly. No brand field,
// no image field, no sale-price field exist on this shape at all
// (docs/stockpilot-gaps.md) -- `unit_cost` is cost price only.
export const productSchema = z.object({
  _provenance: provenanceMap,
  _derivation_ref: provenanceMap,
  sku: z.string(),
  description: z.string().nullable(),
  category_id: z.number().int().nullable(),
  supplier_id: z.number().int().nullable(),
  unit_cost: z.number().nullable(),
  reorder_point: z.number().int().nullable(),
  safety_stock: z.number().int().nullable(),
  created_at: z.string(),
});
export type Product = z.infer<typeof productSchema>;

export const productListResponseSchema = z.array(productSchema);
