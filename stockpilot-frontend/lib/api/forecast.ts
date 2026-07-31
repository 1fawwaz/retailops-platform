import { apiFetch } from "./client";
import { forecastResponseSchema, type SkuForecast } from "../validation/forecast";

// contracts/stockpilot-api: POST /forecast/demand -- request body
// { skus: string[], horizon_days: 1-90 }, verified against v1.json's
// ForecastRequest schema before writing this.
export async function getForecast(sku: string, horizonDays: number): Promise<SkuForecast | null> {
  const raw = await apiFetch<unknown>("/forecast/demand", {
    method: "POST",
    body: { skus: [sku], horizon_days: horizonDays },
  });
  const results = forecastResponseSchema.parse(raw);
  return results.find((result) => result.sku === sku) ?? null;
}
