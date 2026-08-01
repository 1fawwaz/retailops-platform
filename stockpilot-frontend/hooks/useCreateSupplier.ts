"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createSupplier } from "../lib/api/suppliers";

export function useCreateSupplier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createSupplier,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["suppliers"] });
    },
  });
}
