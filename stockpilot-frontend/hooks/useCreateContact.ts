"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createContact } from "../lib/api/suppliers";
import type { SupplierContactFormValues } from "../lib/validation/suppliers";

export function useCreateContact(supplierId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (values: SupplierContactFormValues) => createContact(supplierId, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["supplier-contacts", supplierId] });
    },
  });
}
