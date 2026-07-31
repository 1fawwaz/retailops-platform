"use client";

import { useQuery } from "@tanstack/react-query";
import { getInventoryValuation } from "../lib/api/inventory";

export function useInventoryValuation() {
  return useQuery({
    queryKey: ["inventory-valuation"],
    queryFn: () => getInventoryValuation(),
  });
}
