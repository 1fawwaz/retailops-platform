"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { deleteContact } from "../lib/api/suppliers";

export function useDeleteContact(supplierId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (contactId: number) => deleteContact(supplierId, contactId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["supplier-contacts", supplierId] });
    },
  });
}
