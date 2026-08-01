import { z } from "zod";

// Mirrors list_purchase_orders_route_purchase_orders_get.json's
// PurchaseOrderRead exactly. Minimal -- just enough to render a
// supplier's purchase history list (lib/api/suppliers.ts's consumer);
// the full Purchase Orders module (create/submit/receive) is a separate,
// not-yet-built frontend task.
export const purchaseOrderLineSchema = z.object({
  id: z.number().int(),
  sku: z.string(),
  quantity_ordered: z.number().int(),
  quantity_received: z.number().int(),
  unit_cost: z.number().nullable(),
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
});
export type PurchaseOrder = z.infer<typeof purchaseOrderSchema>;
export const purchaseOrderListResponseSchema = z.array(purchaseOrderSchema);
