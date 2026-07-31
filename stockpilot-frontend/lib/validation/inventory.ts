import { z } from "zod";

const provenanceMap = z.record(z.string(), z.string());

// Mirrors contracts/stockpilot-api/schemas/get_stock_inventory_stock_get.json
// / get_low_stock_inventory_low_stock_get.json exactly (both use the same
// StockItem shape). No warehouse/location field exists -- StockPilot Core
// is single-location today (docs/stockpilot-gaps.md).
export const stockItemSchema = z.object({
  _provenance: provenanceMap,
  _derivation_ref: provenanceMap,
  sku: z.string(),
  description: z.string().nullable(),
  category: z.string().nullable(),
  quantity_on_hand: z.number().int(),
  reorder_point: z.number().int().nullable(),
  safety_stock: z.number().int().nullable(),
  as_of_date: z.string(),
  is_low_stock: z.boolean(),
});
export type StockItem = z.infer<typeof stockItemSchema>;

export const stockListResponseSchema = z.array(stockItemSchema);

// Mirrors contracts/stockpilot-api/schemas/get_inventory_valuation_inventory_valuation_get.json.
export const valuationRowSchema = z.object({
  _provenance: provenanceMap,
  _derivation_ref: provenanceMap,
  category: z.string().nullable(),
  quantity_on_hand: z.number().int(),
  inventory_value: z.number(),
});

export const inventoryValuationSchema = z.object({
  _provenance: provenanceMap,
  _derivation_ref: provenanceMap,
  by_category: z.array(valuationRowSchema),
  total_quantity_on_hand: z.number().int(),
  total_inventory_value: z.number(),
});
export type InventoryValuation = z.infer<typeof inventoryValuationSchema>;
