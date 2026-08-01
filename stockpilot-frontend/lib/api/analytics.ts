import { apiFetch } from "./client";
import { revenueResponseSchema, type RevenuePeriod } from "../validation/analytics";
import { supplierRollupListResponseSchema, type SupplierRollup } from "../validation/suppliers";

// contracts/stockpilot-api: GET /analytics/suppliers -- no query params.
export async function getSupplierRollup(): Promise<SupplierRollup[]> {
  const raw = await apiFetch<unknown>("/analytics/suppliers");
  return supplierRollupListResponseSchema.parse(raw);
}

export type RevenueGroupBy = "day" | "week" | "month" | "category";

// contracts/stockpilot-api: GET /analytics/revenue -- group_by, start_date,
// end_date all optional query params, matching the real OpenAPI parameter
// list exactly (verified against v1.json before writing this).
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
