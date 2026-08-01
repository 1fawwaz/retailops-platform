"use client";

import { useQuery } from "@tanstack/react-query";
import { listSuppliers } from "../lib/api/suppliers";

export function useSuppliers() {
  return useQuery({
    queryKey: ["suppliers"],
    queryFn: () => listSuppliers(),
  });
}
