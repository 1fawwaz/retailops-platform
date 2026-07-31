"use client";

import { useQuery } from "@tanstack/react-query";
import { getSupplier } from "../lib/api/suppliers";

export function useSupplier(supplierId: number | null) {
  return useQuery({
    queryKey: ["supplier", supplierId],
    queryFn: () => getSupplier(supplierId as number),
    enabled: supplierId !== null,
  });
}
