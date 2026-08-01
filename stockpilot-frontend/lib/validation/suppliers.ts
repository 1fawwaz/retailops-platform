import { z } from "zod";

const provenanceMap = z.record(z.string(), z.string());

// Mirrors contracts/stockpilot-api/schemas/get_supplier_route_suppliers__supplier_id__get.json
// exactly. No contacts array -- contacts are a separate sub-resource
// (GET /suppliers/{id}/contacts, see supplierContactSchema below).
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
// -- no `skus` field there (only the detail response has it). Used both
// for the Suppliers list page and lib/api/products.ts's supplier
// dropdown (a strict subset of what it needs).
export const supplierListItemSchema = z.object({
  _provenance: provenanceMap,
  _derivation_ref: provenanceMap,
  id: z.number().int(),
  name: z.string(),
  lead_time_days: z.number().int(),
  reliability_score: z.number(),
  created_at: z.string(),
});
export type SupplierListItem = z.infer<typeof supplierListItemSchema>;
export const supplierListResponseSchema = z.array(supplierListItemSchema);

export const supplierFormSchema = z.object({
  name: z.string().min(1, "Name is required"),
  lead_time_days: z.preprocess(
    (v) => (v === "" || v === undefined ? undefined : Number(v)),
    z.number().int().min(0, "Lead time cannot be negative"),
  ),
  reliability_score: z.preprocess(
    (v) => (v === "" || v === undefined ? undefined : Number(v)),
    z.number().min(0, "Must be between 0 and 1").max(1, "Must be between 0 and 1"),
  ),
});
export type SupplierFormValues = z.infer<typeof supplierFormSchema>;

// Mirrors list_contacts_route_suppliers__supplier_id__contacts_get.json exactly.
export const supplierContactSchema = z.object({
  id: z.number().int(),
  supplier_id: z.number().int(),
  name: z.string(),
  email: z.string().nullable(),
  phone: z.string().nullable(),
  role: z.string().nullable(),
  created_at: z.string(),
});
export type SupplierContact = z.infer<typeof supplierContactSchema>;
export const supplierContactListResponseSchema = z.array(supplierContactSchema);

export const supplierContactFormSchema = z.object({
  name: z.string().min(1, "Name is required"),
  email: z.string().optional(),
  phone: z.string().optional(),
  role: z.string().optional(),
});
export type SupplierContactFormValues = z.infer<typeof supplierContactFormSchema>;

// Mirrors get_supplier_rollup_route_analytics_suppliers_get.json's
// SupplierRollup exactly. on_time_delivery_rate is nullable -- a
// supplier with no received/closed POs yet has no rate to report, not a
// fabricated 0.
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
export const supplierRollupListResponseSchema = z.array(supplierRollupSchema);
