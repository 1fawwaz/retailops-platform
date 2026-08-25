"use client";

import { useQuery } from "@tanstack/react-query";
import { listPurchaseOrders } from "../lib/api/purchaseOrders";
import type { ListParams } from "../lib/api/list-params";

export function usePurchaseOrders(options?: ListParams & { supplierId?: number; status?: string }) {
  return useQuery({
    queryKey: ["purchase-orders", options],
    queryFn: () => listPurchaseOrders(options),
  });
}