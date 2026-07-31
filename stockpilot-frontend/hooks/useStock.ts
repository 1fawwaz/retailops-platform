"use client";

import { useQuery } from "@tanstack/react-query";
import { getStock } from "../lib/api/inventory";

export function useStock(options: {
  category?: string;
  lowStock?: boolean;
  search?: string;
  limit: number;
  offset: number;
}) {
  return useQuery({
    queryKey: ["stock", options],
    queryFn: () => getStock(options),
  });
}
