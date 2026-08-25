"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { receivePurchaseOrder } from "../lib/api/purchaseOrders";
import type { ReceiveRequest } from "../lib/validation/purchaseOrders";

export function useReceivePurchaseOrder(poId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: ReceiveRequest) => receivePurchaseOrder(poId, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
      queryClient.invalidateQueries({ queryKey: ["purchase-order", poId] });
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
      queryClient.invalidateQueries({ queryKey: ["stock"] });
    },
  });
}