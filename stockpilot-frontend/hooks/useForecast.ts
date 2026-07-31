"use client";

import { useQuery } from "@tanstack/react-query";
import { getForecast } from "../lib/api/forecast";

export function useForecast(sku: string, horizonDays: number) {
  return useQuery({
    queryKey: ["forecast", sku, horizonDays],
    queryFn: () => getForecast(sku, horizonDays),
  });
}
