import { z } from "zod";

const provenanceMap = z.record(z.string(), z.string());

// Mirrors contracts/stockpilot-api/schemas/get_supplier_route_suppliers__supplier_id__get.json
// exactly. No contacts array, no performance-history field --
// docs/stockpilot-gaps.md: purchase history and performance metrics
// (BUILD.md Stage 4) have no backend source.
export const supplierSchema = z.object({
  _provenance: provenanceMap,
  _derivation_ref: provenanceMap,
  id: z.number().int(),
  name: z.string(),
  lead_time_days: z.number().int(),
  reliability_score: z.number(),
  created_at: z.string(),
  skus: z.array(z.string()),
});
export type Supplier = z.infer<typeof supplierSchema>;
