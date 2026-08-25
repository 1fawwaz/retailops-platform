import { apiFetch } from "./client";
import type { ListParams } from "./list-params";
import {
  purchaseOrderSchema,
  purchaseOrderListResponseSchema,
  type PurchaseOrder,
  type PurchaseOrderCreate,
  type PurchaseOrderUpdate,
  type ReceiveRequest,
} from "../validation/purchaseOrders";

export async function listPurchaseOrders(options?: ListParams & { supplierId?: number; status?: string }): Promise<PurchaseOrder[]> {
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

export async function getPurchaseOrder(poId: number): Promise<PurchaseOrder> {
  const raw = await apiFetch<unknown>(`/purchase-orders/${poId}`);
  return purchaseOrderSchema.parse(raw);
}

export async function createPurchaseOrder(values: PurchaseOrderCreate): Promise<PurchaseOrder> {
  const raw = await apiFetch<unknown>("/purchase-orders", {
    method: "POST",
    body: values,
  });
  return purchaseOrderSchema.parse(raw);
}

export async function updatePurchaseOrder(poId: number, values: PurchaseOrderUpdate): Promise<PurchaseOrder> {
  const raw = await apiFetch<unknown>(`/purchase-orders/${poId}`, {
    method: "PUT",
    body: values,
  });
  return purchaseOrderSchema.parse(raw);
}

export async function submitPurchaseOrder(poId: number): Promise<PurchaseOrder> {
  const raw = await apiFetch<unknown>(`/purchase-orders/${poId}/submit`, {
    method: "POST",
  });
  return purchaseOrderSchema.parse(raw);
}

export async function approvePurchaseOrder(poId: number): Promise<PurchaseOrder> {
  const raw = await apiFetch<unknown>(`/purchase-orders/${poId}/approve`, {
    method: "POST",
  });
  return purchaseOrderSchema.parse(raw);
}

export async function cancelPurchaseOrder(poId: number): Promise<PurchaseOrder> {
  const raw = await apiFetch<unknown>(`/purchase-orders/${poId}/cancel`, {
    method: "POST",
  });
  return purchaseOrderSchema.parse(raw);
}

export async function closePurchaseOrder(poId: number): Promise<PurchaseOrder> {
  const raw = await apiFetch<unknown>(`/purchase-orders/${poId}/close`, {
    method: "POST",
  });
  return purchaseOrderSchema.parse(raw);
}

export async function receivePurchaseOrder(poId: number, values: ReceiveRequest): Promise<PurchaseOrder> {
  const raw = await apiFetch<unknown>(`/purchase-orders/${poId}/receive`, {
    method: "POST",
    body: values,
  });
  return purchaseOrderSchema.parse(raw);
}