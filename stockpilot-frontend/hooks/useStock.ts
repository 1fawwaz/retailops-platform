"use client";

import { useQuery } from "@tanstack/react-query";
import { getStock } from "../lib/api/inventory";
import type { ListParams } from "../lib/api/list-params";

export function useStock(options: ListParams & { lowStock?: boolean; limit: number; offset: number }) {
  return useQuery({
    queryKey: ["stock", options],
    queryFn: () => getStock(options),
  });
}
