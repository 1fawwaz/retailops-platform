"use client";

import { useQuery } from "@tanstack/react-query";
import { listWarehouses } from "../lib/api/warehouses";

export function useWarehouses() {
  return useQuery({
    queryKey: ["warehouses"],
    queryFn: () => listWarehouses(),
  });
}