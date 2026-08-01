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

// Mirrors list_suppliers_route_suppliers_get.json's SupplierRead exactly
// -- no `skus` field there (only the detail response has it), so this is
// a deliberately separate, leaner schema rather than reusing
// supplierSchema. Minimal fields needed for a name-lookup dropdown
// (lib/api/products.ts's create/edit form); the full Suppliers module
// (BUILD.md, not yet built) can extend this when it lands.
export const supplierListItemSchema = z.object({
  id: z.number().int(),
  name: z.string(),
});
export type SupplierListItem = z.infer<typeof supplierListItemSchema>;
export const supplierListResponseSchema = z.array(supplierListItemSchema);
