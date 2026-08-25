"use client";

import { useQuery } from "@tanstack/react-query";
import { getPurchaseOrder } from "../lib/api/purchaseOrders";

export function usePurchaseOrder(poId: number | null) {
  return useQuery({
    queryKey: ["purchase-order", poId],
    queryFn: () => getPurchaseOrder(poId!),
    enabled: poId !== null,
  });
}