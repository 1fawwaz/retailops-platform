"use client";

import { useQuery } from "@tanstack/react-query";
import { getSupplierRollup } from "../lib/api/analytics";

export function useSupplierRollup() {
  return useQuery({
    queryKey: ["supplier-rollup"],
    queryFn: () => getSupplierRollup(),
  });
}
