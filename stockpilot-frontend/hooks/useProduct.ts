"use client";

import { useQuery } from "@tanstack/react-query";
import { getProduct } from "../lib/api/products";

export function useProduct(sku: string) {
  return useQuery({
    queryKey: ["product", sku],
    queryFn: () => getProduct(sku),
  });
}
