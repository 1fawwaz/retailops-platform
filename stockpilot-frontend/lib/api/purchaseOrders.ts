import { apiFetch } from "./client";
import { purchaseOrderListResponseSchema, type PurchaseOrder } from "../validation/purchaseOrders";

// contracts/stockpilot-api: GET /purchase-orders -- status, supplier_id,
// limit (max 1000), offset.
export async function listPurchaseOrders(options?: {
  supplierId?: number;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<PurchaseOrder[]> {
  const raw = await apiFetch<unknown>("/purchase-orders", {
    params: {
      supplier_id: options?.supplierId,
      status: options?.status,
      limit: options?.limit,
      offset: options?.offset,
    },
  });
  return purchaseOrderListResponseSchema.parse(raw);
}
