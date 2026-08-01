import { apiFetch } from "./client";
import {
  brandListResponseSchema,
  brandSchema,
  type Brand,
  type BrandCreate,
} from "../validation/brand";

export async function listBrands(): Promise<Brand[]> {
  const raw = await apiFetch<unknown>("/brands");
  return brandListResponseSchema.parse(raw);
}

export async function createBrand(data: BrandCreate): Promise<Brand> {
  const raw = await apiFetch<unknown>("/brands", { method: "POST", body: data });
  return brandSchema.parse(raw);
}
