import { apiFetch } from "./client";
import type { ListParams } from "./list-params";
import {
  customerSchema,
  customerListResponseSchema,
  type Customer,
  type CustomerFormValues,
} from "../validation/customers";

export async function listCustomers(options?: ListParams): Promise<Customer[]> {
  const raw = await apiFetch<unknown>("/customers", {
    params: {
      search: options?.search,
      limit: options?.limit,
      offset: options?.offset,
    },
  });
  return customerListResponseSchema.parse(raw);
}

export async function getCustomer(id: number): Promise<Customer> {
  const raw = await apiFetch<unknown>(`/customers/${id}`);
  return customerSchema.parse(raw);
}

export async function createCustomer(values: CustomerFormValues): Promise<Customer> {
  const raw = await apiFetch<unknown>("/customers", {
    method: "POST",
    body: values,
  });
  return customerSchema.parse(raw);
}

export async function updateCustomer(id: number, values: CustomerFormValues): Promise<Customer> {
  const raw = await apiFetch<unknown>(`/customers/${id}`, {
    method: "PUT",
    body: values,
  });
  return customerSchema.parse(raw);
}

export async function deleteCustomer(id: number): Promise<void> {
  await apiFetch<undefined>(`/customers/${id}`, { method: "DELETE" });
}

export async function getCustomerOrders(id: number): Promise<unknown[]> {
  const raw = await apiFetch<unknown>(`/customers/${id}/orders`);
  return raw as unknown[];
}