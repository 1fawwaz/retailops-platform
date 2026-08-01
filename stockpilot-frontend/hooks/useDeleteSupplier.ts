"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { deleteSupplier } from "../lib/api/suppliers";

export function useDeleteSupplier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteSupplier,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["suppliers"] });
    },
  });
}
