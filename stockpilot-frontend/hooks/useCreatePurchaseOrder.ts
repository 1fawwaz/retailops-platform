"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createPurchaseOrder } from "../lib/api/purchaseOrders";
import type { PurchaseOrderCreate } from "../lib/validation/purchaseOrders";

export function useCreatePurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: PurchaseOrderCreate) => createPurchaseOrder(values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
    },
  });
}