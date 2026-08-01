"use client";

import { useQuery } from "@tanstack/react-query";
import { getProductHistory } from "../lib/api/products";

export function useProductHistory(sku: string) {
  return useQuery({
    queryKey: ["product-history", sku],
    queryFn: () => getProductHistory(sku),
  });
}
