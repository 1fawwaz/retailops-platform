import { apiFetch } from "./client";
import { supplierSchema, type Supplier } from "../validation/suppliers";

// contracts/stockpilot-api: GET /suppliers/{supplier_id} -- path param
// is an integer, not a string.
export async function getSupplier(supplierId: number): Promise<Supplier> {
  const raw = await apiFetch<unknown>(`/suppliers/${supplierId}`);
  return supplierSchema.parse(raw);
}
