import { z } from "zod";

const provenanceMap = z.record(z.string(), z.string());

export const revenuePeriodSchema = z.object({
  _provenance: provenanceMap,
  _derivation_ref: provenanceMap,
  period: z.string(),
  revenue: z.number(),
  units: z.number().int(),
});
export type RevenuePeriod = z.infer<typeof revenuePeriodSchema>;

export const revenueResponseSchema = z.array(revenuePeriodSchema);

export const profitPeriodSchema = z.object({
  _provenance: provenanceMap,
  _derivation_ref: provenanceMap,
  period: z.string(),
  profit: z.number(),
  margin_pct: z.number(),
});
export type ProfitPeriod = z.infer<typeof profitPeriodSchema>;

export const profitResponseSchema = z.array(profitPeriodSchema);

export const turnoverRowSchema = z.object({
  _provenance: provenanceMap,
  _derivation_ref: provenanceMap,
  sku: z.string(),
  description: z.string().nullable(),
  turnover_ratio: z.number(),
  avg_stock_on_hand: z.number(),
});
export type TurnoverRow = z.infer<typeof turnoverRowSchema>;

export const turnoverResponseSchema = z.array(turnoverRowSchema);

export const abcRowSchema = z.object({
  _provenance: provenanceMap,
  _derivation_ref: provenanceMap,
  sku: z.string(),
  revenue: z.number(),
  cumulative_pct: z.number(),
  abc_class: z.string(),
});
export type AbcRow = z.infer<typeof abcRowSchema>;

export const abcResponseSchema = z.array(abcRowSchema);

export const topBottomProductSchema = z.object({
  _provenance: provenanceMap,
  _derivation_ref: provenanceMap,
  sku: z.string(),
  description: z.string().nullable(),
  units: z.number().int(),
  revenue: z.number(),
  margin_pct: z.number().nullable(),
});
export type TopBottomProduct = z.infer<typeof topBottomProductSchema>;

export const topBottomProductsResponseSchema = z.array(topBottomProductSchema);

export const periodComparisonSchema = z.object({
  _provenance: provenanceMap,
  _derivation_ref: provenanceMap,
  metric: z.string(),
  current: z.number(),
  prior: z.number(),
  change_pct: z.number(),
});
export type PeriodComparison = z.infer<typeof periodComparisonSchema>;

export const periodComparisonResponseSchema = z.array(periodComparisonSchema);

export const supplierRollupSchema = z.object({
  _provenance: provenanceMap,
  _derivation_ref: provenanceMap,
  supplier_id: z.number().int(),
  name: z.string(),
  lead_time_days: z.number().int(),
  reliability_score: z.number(),
  sku_count: z.number().int(),
  total_inventory_value: z.number(),
  open_purchase_order_count: z.number().int(),
  total_purchase_order_count: z.number().int(),
  on_time_delivery_rate: z.number().nullable(),
});
export type SupplierRollup = z.infer<typeof supplierRollupSchema>;

export const supplierRollupResponseSchema = z.array(supplierRollupSchema);

export const purchaseOrderKpisSchema = z.object({
  _provenance: provenanceMap,
  _derivation_ref: provenanceMap,
  open_purchase_order_count: z.number().int(),
  avg_days_to_receive: z.number().nullable(),
});
export type PurchaseOrderKpis = z.infer<typeof purchaseOrderKpisSchema>;

export const purchaseOrderKpisResponseSchema = purchaseOrderKpisSchema;

export const deadStockItemSchema = z.object({
  _provenance: provenanceMap,
  _derivation_ref: provenanceMap,
  sku: z.string(),
  description: z.string().nullable(),
  quantity_on_hand: z.number().int(),
  last_movement_date: z.string().nullable(),
  days_since_movement: z.number().int().nullable(),
});
export type DeadStockItem = z.infer<typeof deadStockItemSchema>;

export const deadStockResponseSchema = z.array(deadStockItemSchema);

export const slowMoverItemSchema = z.object({
  _provenance: provenanceMap,
  _derivation_ref: provenanceMap,
  sku: z.string(),
  description: z.string().nullable(),
  quantity_on_hand: z.number().int(),
  units_sold: z.number().int(),
  avg_daily_demand: z.number(),
});
export type SlowMoverItem = z.infer<typeof slowMoverItemSchema>;

export const slowMoversResponseSchema = z.array(slowMoverItemSchema);

export const valuationRowSchema = z.object({
  _provenance: provenanceMap,
  _derivation_ref: provenanceMap,
  category: z.string().nullable(),
  quantity_on_hand: z.number().int(),
  inventory_value: z.number(),
});
export type ValuationRow = z.infer<typeof valuationRowSchema>;

export const inventoryValuationSchema = z.object({
  _provenance: provenanceMap,
  _derivation_ref: provenanceMap,
  by_category: z.array(valuationRowSchema),
  total_quantity_on_hand: z.number().int(),
  total_inventory_value: z.number(),
});
export type InventoryValuation = z.infer<typeof inventoryValuationSchema>;

export const inventoryValuationResponseSchema = inventoryValuationSchema;