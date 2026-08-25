"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { submitPurchaseOrder } from "../lib/api/purchaseOrders";

export function useSubmitPurchaseOrder(poId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => submitPurchaseOrder(poId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      queryClient.invalidateQueries({ queryKey: ["purchase-order", poId] });
    },
  });
}