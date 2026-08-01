"use client";

import { useQuery } from "@tanstack/react-query";
import { listBrands } from "../lib/api/brands";

export function useBrands() {
  return useQuery({
    queryKey: ["brands"],
    queryFn: () => listBrands(),
  });
}
