import { apiFetch } from "./client";
import {
  inventoryValuationSchema,
  stockListResponseSchema,
  type InventoryValuation,
  type StockItem,
} from "../validation/inventory";

// contracts/stockpilot-api: GET /inventory/stock -- category, low_stock,
// search, limit (max 1000), offset. Query params verified against
// v1.json before writing this, not assumed.
export async function getStock(options?: {
  category?: string;
  lowStock?: boolean;
  search?: string;
  limit?: number;
  offset?: number;
}): Promise<StockItem[]> {
  const raw = await apiFetch<unknown>("/inventory/stock", {
    params: {
      category: options?.category,
      low_stock: options?.lowStock,
      search: options?.search,
      limit: options?.limit,
      offset: options?.offset,
    },
  });
  return stockListResponseSchema.parse(raw);
}

const LOW_STOCK_MAX_LIMIT = 1000;

export interface LowStockCount {
  count: number;
  /**
   * True if `count` is a lower bound, not an exact total -- the response
   * hit the API's own hard page-size cap (1000) with no total/has-more
   * field to confirm whether more rows exist beyond it. Never silently
   * presented as an exact count when this is true (docs/PRODUCT-SPEC.md
   * §13's honesty rule) -- the caller must render it as "1000+", not "1000".
   */
  isLowerBound: boolean;
}

/**
 * GET /inventory/low-stock has no dedicated count endpoint and no
 * total/has-more field in its response -- it's a bare, paginated array
 * (max limit 1000). Fetching at the max limit and using .length is the
 * only real way to get this number, but it can silently undercount if
 * the true total exceeds 1000; this function makes that boundary
 * explicit instead of hiding it, per the instruction not to approximate
 * a missing capability client-side.
 */
export async function getLowStockCount(): Promise<LowStockCount> {
  const raw = await apiFetch<unknown>("/inventory/low-stock", {
    params: { limit: LOW_STOCK_MAX_LIMIT, offset: 0 },
  });
  const items = stockListResponseSchema.parse(raw);
  return { count: items.length, isLowerBound: items.length === LOW_STOCK_MAX_LIMIT };
}

// contracts/stockpilot-api: GET /inventory/valuation -- category optional.
export async function getInventoryValuation(options?: {
  category?: string;
}): Promise<InventoryValuation> {
  const raw = await apiFetch<unknown>("/inventory/valuation", {
    params: { category: options?.category },
  });
  return inventoryValuationSchema.parse(raw);
}
