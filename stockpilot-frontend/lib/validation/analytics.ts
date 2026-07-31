import { z } from "zod";

// Mirrors contracts/stockpilot-api/schemas/get_revenue_route_analytics_revenue_get.json
// exactly. `_provenance`/`_derivation_ref` are StockPilot Core's own
// per-field provenance labels (docs/PRODUCT-SPEC.md §13) -- kept as
// loosely-typed maps, not stripped, so the UI can surface them.
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
