"use client";

import { useQuery } from "@tanstack/react-query";
import { listPurchaseOrders } from "../lib/api/purchaseOrders";

export function useSupplierPurchaseOrders(supplierId: number) {
  return useQuery({
    queryKey: ["purchase-orders", { supplierId }],
    queryFn: () => listPurchaseOrders({ supplierId, limit: 50 }),
  });
}
