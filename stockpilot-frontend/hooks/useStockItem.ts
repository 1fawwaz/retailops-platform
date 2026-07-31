"use client";

import { useQuery } from "@tanstack/react-query";
import { getStock } from "../lib/api/inventory";

/**
 * There is no GET /inventory/stock/{sku} single-item endpoint
 * (docs/stockpilot-gaps.md) -- only the list endpoint with a `search`
 * param. This uses that, then filters for an exact SKU match against
 * the (small) result set -- a precise lookup from real, already-fetched
 * data, not a guess. Returns undefined (not an error) if no exact match
 * comes back, distinguished from isPending/isError by the caller.
 */
export function useStockItem(sku: string) {
  return useQuery({
    queryKey: ["stock-item", sku],
    queryFn: async () => {
      const results = await getStock({ search: sku, limit: 25, offset: 0 });
      return results.find((item) => item.sku === sku) ?? null;
    },
  });
}
