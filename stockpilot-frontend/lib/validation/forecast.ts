import { z } from "zod";

const provenanceMap = z.record(z.string(), z.string());

// Mirrors contracts/stockpilot-api/schemas/post_forecast_demand_forecast_demand_post.json
// exactly. A single predicted-daily-demand point with a confidence
// interval, not a per-day time series -- BUILD.md Stage 7's actual
// forecast chart needs more design than this endpoint alone provides;
// Stage 2's "linked forecast" on Inventory Details only needs this one
// point, which this shape already supports.
export const skuForecastSchema = z.object({
  _provenance: provenanceMap,
  _derivation_ref: provenanceMap,
  sku: z.string(),
  predicted_daily_demand: z.number(),
  confidence_interval_lower: z.number(),
  confidence_interval_upper: z.number(),
  model_used: z.string(),
  training_window_start: z.string().nullable(),
  training_window_end: z.string().nullable(),
  data_quality: z.string(),
});
export type SkuForecast = z.infer<typeof skuForecastSchema>;

export const forecastResponseSchema = z.array(skuForecastSchema);

export const forecastRequestSchema = z.object({
  skus: z.array(z.string()).min(1),
  horizon_days: z.number().int().min(1).max(90),
});
export type ForecastRequest = z.infer<typeof forecastRequestSchema>;
