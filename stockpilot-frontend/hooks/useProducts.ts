"use client";

import { useQuery } from "@tanstack/react-query";
import { listProducts } from "../lib/api/products";
import type { ListParams } from "../lib/api/list-params";

export function useProducts(options: ListParams) {
  return useQuery({
    queryKey: ["products", options],
    queryFn: () => listProducts(options),
  });
}
