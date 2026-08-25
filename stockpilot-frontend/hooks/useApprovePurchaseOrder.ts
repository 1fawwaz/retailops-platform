"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { approvePurchaseOrder } from "../lib/api/purchaseOrders";

export function useApprovePurchaseOrder(poId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => approvePurchaseOrder(poId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      queryClient.invalidateQueries({ queryKey: ["purchase-order", poId] });
    },
  });
}