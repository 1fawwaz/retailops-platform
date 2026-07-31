import { apiFetch } from "./client";
import { productSchema, type Product } from "../validation/products";

// contracts/stockpilot-api: GET /products/{sku} -- no query params.
export async function getProduct(sku: string): Promise<Product> {
  const raw = await apiFetch<unknown>(`/products/${encodeURIComponent(sku)}`);
  return productSchema.parse(raw);
}
