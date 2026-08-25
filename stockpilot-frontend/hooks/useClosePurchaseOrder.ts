"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { closePurchaseOrder } from "../lib/api/purchaseOrders";

export function useClosePurchaseOrder(poId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => closePurchaseOrder(poId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      queryClient.invalidateQueries({ queryKey: ["purchase-order", poId] });
    },
  });
}