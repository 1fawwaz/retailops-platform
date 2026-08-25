import { apiFetch } from "./client";
import { warehouseListResponseSchema, type Warehouse } from "../validation/warehouses";

export async function listWarehouses(): Promise<Warehouse[]> {
  const raw = await apiFetch<unknown>("/warehouses");
  return warehouseListResponseSchema.parse(raw);
}