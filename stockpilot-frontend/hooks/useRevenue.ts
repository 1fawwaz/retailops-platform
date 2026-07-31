"use client";

import { useQuery } from "@tanstack/react-query";
import { getRevenue, type RevenueGroupBy } from "../lib/api/analytics";

export function useRevenue(options?: {
  groupBy?: RevenueGroupBy;
  startDate?: string;
  endDate?: string;
}) {
  return useQuery({
    queryKey: ["revenue", options ?? {}],
    queryFn: () => getRevenue(options),
  });
}
