"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateSupplier } from "../lib/api/suppliers";
import type { SupplierFormValues } from "../lib/validation/suppliers";

export function useUpdateSupplier(supplierId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: SupplierFormValues) => updateSupplier(supplierId, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["suppliers"] });
      queryClient.invalidateQueries({ queryKey: ["supplier", supplierId] });
    },
  });
}
