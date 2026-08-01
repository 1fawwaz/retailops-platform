"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateProduct } from "../lib/api/products";
import type { ProductFormValues } from "../lib/validation/products";

export function useUpdateProduct(sku: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: Omit<ProductFormValues, "sku">) => updateProduct(sku, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["product", sku] });
      queryClient.invalidateQueries({ queryKey: ["product-history", sku] });
    },
  });
}
