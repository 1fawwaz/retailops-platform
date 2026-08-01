import { apiFetch } from "./client";
import type { ListParams } from "./list-params";
import {
  productDetailSchema,
  productHistoryResponseSchema,
  productListResponseSchema,
  productSchema,
  type Product,
  type ProductDetail,
  type ProductFormValues,
  type ProductHistoryEntry,
} from "../validation/products";

// contracts/stockpilot-api: GET /products -- search, category, limit
// (max 1000), offset. Query params verified against v1.json after the
// backend was extended to support them (see commit 1179357).
export async function listProducts(options?: ListParams): Promise<Product[]> {
  const raw = await apiFetch<unknown>("/products", {
    params: {
      search: options?.search,
      category: options?.category,
      limit: options?.limit,
      offset: options?.offset,
    },
  });
  return productListResponseSchema.parse(raw);
}

// GET /products/{sku} returns ProductDetail (quantity_on_hand +
// movement_history included), not the leaner list-row Product shape --
// validating against productDetailSchema means a caller that only needs
// the Product fields still gets them (ProductDetail is a strict
// superset), and callers needing the detail fields no longer have to
// re-fetch or assume shapes this function already received.
export async function getProduct(sku: string): Promise<ProductDetail> {
  const raw = await apiFetch<unknown>(`/products/${encodeURIComponent(sku)}`);
  return productDetailSchema.parse(raw);
}

export async function createProduct(values: ProductFormValues): Promise<Product> {
  const raw = await apiFetch<unknown>("/products", {
    method: "POST",
    body: { ...values, description: values.description || null },
  });
  return productSchema.parse(raw);
}

// PUT /products/{sku}'s body has no sku field (only the URL path does)
// -- omitted from the type and never sent, not just ignored server-side.
export async function updateProduct(
  sku: string,
  values: Omit<ProductFormValues, "sku">,
): Promise<Product> {
  const raw = await apiFetch<unknown>(`/products/${encodeURIComponent(sku)}`, {
    method: "PUT",
    body: { ...values, description: values.description || null },
  });
  return productSchema.parse(raw);
}

export async function deleteProduct(sku: string): Promise<void> {
  await apiFetch<undefined>(`/products/${encodeURIComponent(sku)}`, { method: "DELETE" });
}

export async function getProductHistory(sku: string): Promise<ProductHistoryEntry[]> {
  const raw = await apiFetch<unknown>(`/products/${encodeURIComponent(sku)}/history`);
  return productHistoryResponseSchema.parse(raw);
}
