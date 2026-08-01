import { apiFetch } from "./client";
import {
  categoryListResponseSchema,
  categorySchema,
  type Category,
  type CategoryCreate,
} from "../validation/category";

export async function listCategories(): Promise<Category[]> {
  const raw = await apiFetch<unknown>("/categories");
  return categoryListResponseSchema.parse(raw);
}

export async function createCategory(data: CategoryCreate): Promise<Category> {
  const raw = await apiFetch<unknown>("/categories", { method: "POST", body: data });
  return categorySchema.parse(raw);
}
