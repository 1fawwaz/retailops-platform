"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { cancelPurchaseOrder } from "../lib/api/purchaseOrders";

export function useCancelPurchaseOrder(poId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => cancelPurchaseOrder(poId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      queryClient.invalidateQueries({ queryKey: ["purchase-order", poId] });
    },
  });
}