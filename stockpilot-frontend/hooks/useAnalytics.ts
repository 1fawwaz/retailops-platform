"use client";

import { useQuery } from "@tanstack/react-query";
import type { RevenueGroupBy } from "../lib/api/analytics";
import {
  getRevenue,
  getProfit,
  getTurnover,
  getAbc,
  getTopProducts,
  getBottomProducts,
  getPeriodComparison,
  getSupplierRollup,
  getPurchaseOrderKpis,
  getDeadStock,
  getSlowMovers,
  getInventoryValuation,
} from "../lib/api/analytics";

export function useRevenue(options?: { groupBy?: RevenueGroupBy; startDate?: string; endDate?: string }) {
  return useQuery({
    queryKey: ["analytics", "revenue", options],
    queryFn: () => getRevenue(options),
  });
}

export function useProfit(options?: { groupBy?: RevenueGroupBy; startDate?: string; endDate?: string }) {
  return useQuery({
    queryKey: ["analytics", "profit", options],
    queryFn: () => getProfit(options),
  });
}

export function useTurnover() {
  return useQuery({
    queryKey: ["analytics", "turnover"],
    queryFn: () => getTurnover(),
  });
}

export function useAbc() {
  return useQuery({
    queryKey: ["analytics", "abc"],
    queryFn: () => getAbc(),
  });
}

export function useTopProducts(limit = 10) {
  return useQuery({
    queryKey: ["analytics", "top-products", limit],
    queryFn: () => getTopProducts(limit),
  });
}

export function useBottomProducts(limit = 10) {
  return useQuery({
    queryKey: ["analytics", "bottom-products", limit],
    queryFn: () => getBottomProducts(limit),
  });
}

export function usePeriodComparison(options?: { metric?: string; startDate?: string; endDate?: string }) {
  return useQuery({
    queryKey: ["analytics", "period-comparison", options],
    queryFn: () => getPeriodComparison(options),
  });
}

export function useSupplierRollup() {
  return useQuery({
    queryKey: ["analytics", "supplier-rollup"],
    queryFn: () => getSupplierRollup(),
  });
}

export function usePurchaseOrderKpis() {
  return useQuery({
    queryKey: ["analytics", "purchase-order-kpis"],
    queryFn: () => getPurchaseOrderKpis(),
  });
}

export function useDeadStock() {
  return useQuery({
    queryKey: ["analytics", "dead-stock"],
    queryFn: () => getDeadStock(),
  });
}

export function useSlowMovers() {
  return useQuery({
    queryKey: ["analytics", "slow-movers"],
    queryFn: () => getSlowMovers(),
  });
}

export function useInventoryValuation() {
  return useQuery({
    queryKey: ["analytics", "inventory-valuation"],
    queryFn: () => getInventoryValuation(),
  });
}