import { apiFetch } from "./client";
import type { ListParams } from "./list-params";
import {
  salesOrderSchema,
  salesOrderListResponseSchema,
  type SalesOrder,
  type SalesOrderFormValues,
} from "../validation/salesOrders";

export async function listSalesOrders(options?: ListParams): Promise<SalesOrder[]> {
  const raw = await apiFetch<unknown>("/sales-orders", {
    params: {
      search: options?.search,
      status: options?.status,
      limit: options?.limit,
      offset: options?.offset,
    },
  });
  return salesOrderListResponseSchema.parse(raw);
}

export async function getSalesOrder(id: number): Promise<SalesOrder> {
  const raw = await apiFetch<unknown>(`/sales-orders/${id}`);
  return salesOrderSchema.parse(raw);
}

export async function createSalesOrder(values: SalesOrderFormValues): Promise<SalesOrder> {
  const raw = await apiFetch<unknown>("/sales-orders", {
    method: "POST",
    body: values,
  });
  return salesOrderSchema.parse(raw);
}

export async function updateSalesOrder(id: number, values: SalesOrderFormValues): Promise<SalesOrder> {
  const raw = await apiFetch<unknown>(`/sales-orders/${id}`, {
    method: "PUT",
    body: values,
  });
  return salesOrderSchema.parse(raw);
}

export async function deleteSalesOrder(id: number): Promise<void> {
  await apiFetch<undefined>(`/sales-orders/${id}`, { method: "DELETE" });
}

export async function confirmSalesOrder(id: number): Promise<SalesOrder> {
  const raw = await apiFetch<unknown>(`/sales-orders/${id}/confirm`, { method: "POST" });
  return salesOrderSchema.parse(raw);
}

export async function cancelSalesOrder(id: number): Promise<SalesOrder> {
  const raw = await apiFetch<unknown>(`/sales-orders/${id}/cancel`, { method: "POST" });
  return salesOrderSchema.parse(raw);
}

export async function fulfillSalesOrder(id: number): Promise<SalesOrder> {
  const raw = await apiFetch<unknown>(`/sales-orders/${id}/fulfill`, { method: "POST" });
  return salesOrderSchema.parse(raw);
}