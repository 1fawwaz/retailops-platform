"use client";

import { useQuery } from "@tanstack/react-query";
import { listContacts } from "../lib/api/suppliers";

export function useSupplierContacts(supplierId: number) {
  return useQuery({
    queryKey: ["supplier-contacts", supplierId],
    queryFn: () => listContacts(supplierId),
  });
}
