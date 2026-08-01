import { apiFetch } from "./client";
import {
  supplierSchema,
  supplierListResponseSchema,
  supplierContactListResponseSchema,
  supplierContactSchema,
  type Supplier,
  type SupplierListItem,
  type SupplierFormValues,
  type SupplierContact,
  type SupplierContactFormValues,
} from "../validation/suppliers";

// contracts/stockpilot-api: GET /suppliers/{supplier_id} -- path param
// is an integer, not a string.
export async function getSupplier(supplierId: number): Promise<Supplier> {
  const raw = await apiFetch<unknown>(`/suppliers/${supplierId}`);
  return supplierSchema.parse(raw);
}

export async function listSuppliers(): Promise<SupplierListItem[]> {
  const raw = await apiFetch<unknown>("/suppliers");
  return supplierListResponseSchema.parse(raw);
}

export async function createSupplier(values: SupplierFormValues): Promise<SupplierListItem> {
  const raw = await apiFetch<unknown>("/suppliers", { method: "POST", body: values });
  return supplierSchema.omit({ skus: true }).parse(raw);
}

export async function updateSupplier(
  supplierId: number,
  values: SupplierFormValues,
): Promise<SupplierListItem> {
  const raw = await apiFetch<unknown>(`/suppliers/${supplierId}`, {
    method: "PUT",
    body: values,
  });
  return supplierSchema.omit({ skus: true }).parse(raw);
}

export async function deleteSupplier(supplierId: number): Promise<void> {
  await apiFetch<undefined>(`/suppliers/${supplierId}`, { method: "DELETE" });
}

export async function listContacts(supplierId: number): Promise<SupplierContact[]> {
  const raw = await apiFetch<unknown>(`/suppliers/${supplierId}/contacts`);
  return supplierContactListResponseSchema.parse(raw);
}

export async function createContact(
  supplierId: number,
  values: SupplierContactFormValues,
): Promise<SupplierContact> {
  const raw = await apiFetch<unknown>(`/suppliers/${supplierId}/contacts`, {
    method: "POST",
    body: { ...values, email: values.email || null, phone: values.phone || null, role: values.role || null },
  });
  return supplierContactSchema.parse(raw);
}

export async function updateContact(
  supplierId: number,
  contactId: number,
  values: Partial<SupplierContactFormValues>,
): Promise<SupplierContact> {
  const raw = await apiFetch<unknown>(`/suppliers/${supplierId}/contacts/${contactId}`, {
    method: "PUT",
    body: values,
  });
  return supplierContactSchema.parse(raw);
}

export async function deleteContact(supplierId: number, contactId: number): Promise<void> {
  await apiFetch<undefined>(`/suppliers/${supplierId}/contacts/${contactId}`, {
    method: "DELETE",
  });
}
