"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updatePurchaseOrder } from "../lib/api/purchaseOrders";
import type { PurchaseOrderUpdate } from "../lib/validation/purchaseOrders";

export function useUpdatePurchaseOrder(poId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: PurchaseOrderUpdate) => updatePurchaseOrder(poId, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      queryClient.invalidateQueries({ queryKey: ["purchase-order", poId] });
    },
  });
}