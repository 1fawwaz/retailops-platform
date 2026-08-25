import { apiFetch } from "./client";
import {
  revenueResponseSchema,
  type RevenuePeriod,
  profitResponseSchema,
  type ProfitPeriod,
  turnoverResponseSchema,
  type TurnoverRow,
  abcResponseSchema,
  type AbcRow,
  topBottomProductsResponseSchema,
  type TopBottomProduct,
  periodComparisonResponseSchema,
  type PeriodComparison,
  supplierRollupResponseSchema,
  type SupplierRollup,
  purchaseOrderKpisResponseSchema,
  type PurchaseOrderKpis,
  deadStockResponseSchema,
  type DeadStockItem,
  slowMoversResponseSchema,
  type SlowMoverItem,
  inventoryValuationResponseSchema,
  type InventoryValuation,
} from "../validation/analytics";

export type RevenueGroupBy = "day" | "week" | "month" | "category";

export async function getRevenue(options?: {
  groupBy?: RevenueGroupBy;
  startDate?: string;
  endDate?: string;
}): Promise<RevenuePeriod[]> {
  const raw = await apiFetch<unknown>("/analytics/revenue", {
    params: {
      group_by: options?.groupBy,
      start_date: options?.startDate,
      end_date: options?.endDate,
    },
  });
  return revenueResponseSchema.parse(raw);
}

export async function getProfit(options?: {
  groupBy?: RevenueGroupBy;
  startDate?: string;
  endDate?: string;
}): Promise<ProfitPeriod[]> {
  const raw = await apiFetch<unknown>("/analytics/profit", {
    params: {
      group_by: options?.groupBy,
      start_date: options?.startDate,
      end_date: options?.endDate,
    },
  });
  return profitResponseSchema.parse(raw);
}

export async function getTurnover(): Promise<TurnoverRow[]> {
  const raw = await apiFetch<unknown>("/analytics/turnover");
  return turnoverResponseSchema.parse(raw);
}

export async function getAbc(): Promise<AbcRow[]> {
  const raw = await apiFetch<unknown>("/analytics/abc");
  return abcResponseSchema.parse(raw);
}

export async function getTopProducts(limit = 10): Promise<TopBottomProduct[]> {
  const raw = await apiFetch<unknown>("/analytics/top-products", {
    params: { limit },
  });
  return topBottomProductsResponseSchema.parse(raw);
}

export async function getBottomProducts(limit = 10): Promise<TopBottomProduct[]> {
  const raw = await apiFetch<unknown>("/analytics/bottom-products", {
    params: { limit },
  });
  return topBottomProductsResponseSchema.parse(raw);
}

export async function getPeriodComparison(options?: {
  metric?: string;
  startDate?: string;
  endDate?: string;
}): Promise<PeriodComparison[]> {
  const raw = await apiFetch<unknown>("/analytics/period-comparison", {
    params: {
      metric: options?.metric,
      start_date: options?.startDate,
      end_date: options?.endDate,
    },
  });
  return periodComparisonResponseSchema.parse(raw);
}

export async function getSupplierRollup(): Promise<SupplierRollup[]> {
  const raw = await apiFetch<unknown>("/analytics/suppliers");
  return supplierRollupResponseSchema.parse(raw);
}

export async function getPurchaseOrderKpis(): Promise<PurchaseOrderKpis> {
  const raw = await apiFetch<unknown>("/analytics/purchase-order-kpis");
  return purchaseOrderKpisResponseSchema.parse(raw);
}

export async function getDeadStock(): Promise<DeadStockItem[]> {
  const raw = await apiFetch<unknown>("/inventory/dead-stock");
  return deadStockResponseSchema.parse(raw);
}

export async function getSlowMovers(): Promise<SlowMoverItem[]> {
  const raw = await apiFetch<unknown>("/inventory/slow-movers");
  return slowMoversResponseSchema.parse(raw);
}

export async function getInventoryValuation(): Promise<InventoryValuation> {
  const raw = await apiFetch<unknown>("/inventory/valuation");
  return inventoryValuationResponseSchema.parse(raw);
}