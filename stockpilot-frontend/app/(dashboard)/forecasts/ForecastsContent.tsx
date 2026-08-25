"use client";

import { useState } from "react";
import { useForecast } from "../../../hooks/useForecast";
import { DataTable, type DataTableColumn } from "../../../components/data-table/DataTable";
import { EmptyState } from "../../../components/ui/EmptyState";
import { formatInteger, formatPercent } from "../../../lib/format";
import { AppError } from "../../../lib/api/errors";

interface ForecastRow {
  sku: string;
  predicted_daily_demand: number;
  confidence_interval_lower: number;
  confidence_interval_upper: number;
  model_used: string;
  data_quality: string;
}

export function ForecastsContent() {
  const [skus, setSkus] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [forecastData, setForecastData] = useState<ForecastRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate(event: React.FormEvent) {
    event.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      const skuList = skus.split(",").map((s) => s.trim()).filter(Boolean);
      if (skuList.length === 0) {
        setError("Please enter at least one SKU.");
        return;
      }
      // The forecast endpoint accepts an array of SKUs
      // We'll need to call it for each SKU or batch
      // For now, let's call it with the first SKU
      // In a real implementation, we'd batch them
      const response = await fetch(`/api/forecast/demand`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ skus: skuList }),
      });
      if (!response.ok) {
        throw new Error("Failed to generate forecast");
      }
      const data = await response.json();
      setForecastData(data);
    } catch (err) {
      setError(err instanceof AppError ? err.message : "Could not generate forecast.");
    } finally {
      setIsLoading(false);
    }
  }

  const columns: DataTableColumn<ForecastRow>[] = [
    { key: "sku", header: "SKU", render: (row) => <span data-numeric className="font-mono">{row.sku}</span> },
    { key: "predicted_daily_demand", header: "Predicted Daily Demand", numeric: true, render: (row) => row.predicted_daily_demand.toFixed(2) },
    { key: "confidence_interval_lower", header: "CI Lower", numeric: true, render: (row) => row.confidence_interval_lower.toFixed(2) },
    { key: "confidence_interval_upper", header: "CI Upper", numeric: true, render: (row) => row.confidence_interval_upper.toFixed(2) },
    { key: "model_used", header: "Model", render: (row) => row.model_used },
    { key: "data_quality", header: "Data Quality", render: (row) => row.data_quality },
  ];

  return (
    <div className="flex flex-col gap-6 pt-4">
      <h1 className="text-[20px] text-[var(--color-text-hi)]">Demand Forecasts</h1>
      <p className="text-[13px] text-[var(--color-text-mid)]">
        Generate demand forecasts for one or more SKUs. Enter SKUs separated by commas.
      </p>

      <form onSubmit={handleGenerate} className="flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[300px]">
          <label htmlFor="skus" className="mb-1 block text-[13px] text-[var(--color-text-mid)]">
            SKUs (comma-separated)
          </label>
          <input
            id="skus"
            value={skus}
            onChange={(event) => setSkus(event.target.value)}
            placeholder="e.g. 85048, 85049, 85050"
            className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-canvas)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] w-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
          />
        </div>
        <button
          type="submit"
          disabled={isLoading}
          className="rounded-[6px] bg-[var(--color-accent)] px-3 py-1.5 text-[13px] text-[var(--color-canvas)] disabled:opacity-60 transition-colors duration-150 hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
        >
          {isLoading ? "Generating…" : "Generate Forecast"}
        </button>
      </form>

      {error && (
        <p className="text-[13px] text-[var(--color-danger)]">{error}</p>
      )}

      {forecastData.length > 0 && (
        <DataTable
          columns={columns}
          rows={forecastData}
          getRowId={(row) => row.sku}
          isLoading={isLoading}
          emptyState={
            <EmptyState title="No forecast data" description="Enter SKUs above and click Generate Forecast." />
          }
        />
      )}
    </div>
  );
}