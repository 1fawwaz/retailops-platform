"use client";

import { useQuery } from "@tanstack/react-query";
import { getLowStockCount } from "../lib/api/inventory";

export function useLowStockCount() {
  return useQuery({
    queryKey: ["low-stock-count"],
    queryFn: () => getLowStockCount(),
  });
}
