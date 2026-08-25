"use client";

import { useState } from "react";
import { useRevenue, useProfit, useTurnover, useAbc, useDeadStock, useSlowMovers, useInventoryValuation, useSupplierRollup } from "../../../hooks/useAnalytics";
import { DataTable, type DataTableColumn } from "../../../components/data-table/DataTable";
import { EmptyState } from "../../../components/ui/EmptyState";
import { toCsv, downloadCsv } from "../../../lib/csv";
import { formatCurrencyPrecise, formatInteger, formatPercent } from "../../../lib/format";
import { AppError } from "../../../lib/api/errors";

interface ReportConfig {
  key: string;
  title: string;
  columns: DataTableColumn<Record<string, unknown>>[];
  getRowId: (row: Record<string, unknown>) => string;
  csvColumns: string[];
}

const REPORTS: ReportConfig[] = [
  {
    key: "revenue",
    title: "Revenue by Month",
    columns: [
      { key: "period", header: "Month", render: (row) => String(row.period) },
      { key: "revenue", header: "Revenue", numeric: true, render: (row) => formatCurrencyPrecise(row.revenue as number) },
      { key: "units", header: "Units", numeric: true, render: (row) => formatInteger(row.units as number) },
    ],
    getRowId: (row) => String(row.period),
    csvColumns: ["period", "revenue", "units"],
  },
  {
    key: "profit",
    title: "Profit by Month",
    columns: [
      { key: "period", header: "Month", render: (row) => String(row.period) },
      { key: "profit", header: "Profit", numeric: true, render: (row) => formatCurrencyPrecise(row.profit as number) },
      { key: "margin_pct", header: "Margin %", numeric: true, render: (row) => formatPercent(row.margin_pct as number) },
    ],
    getRowId: (row) => String(row.period),
    csvColumns: ["period", "profit", "margin_pct"],
  },
  {
    key: "turnover",
    title: "Inventory Turnover",
    columns: [
      { key: "sku", header: "SKU", render: (row) => String(row.sku) },
      { key: "description", header: "Description", render: (row) => String(row.description ?? "—") },
      { key: "turnover_ratio", header: "Turnover Ratio", numeric: true, render: (row) => (row.turnover_ratio as number).toFixed(2) },
      { key: "avg_stock_on_hand", header: "Avg Stock on Hand", numeric: true, render: (row) => formatInteger(row.avg_stock_on_hand as number) },
    ],
    getRowId: (row) => String(row.sku),
    csvColumns: ["sku", "description", "turnover_ratio", "avg_stock_on_hand"],
  },
  {
    key: "abc",
    title: "ABC Classification",
    columns: [
      { key: "sku", header: "SKU", render: (row) => String(row.sku) },
      { key: "revenue", header: "Revenue", numeric: true, render: (row) => formatCurrencyPrecise(row.revenue as number) },
      { key: "cumulative_pct", header: "Cumulative %", numeric: true, render: (row) => formatPercent((row.cumulative_pct as number) * 100) },
      { key: "abc_class", header: "ABC Class", render: (row) => String(row.abc_class) },
    ],
    getRowId: (row) => String(row.sku),
    csvColumns: ["sku", "revenue", "cumulative_pct", "abc_class"],
  },
  {
    key: "dead-stock",
    title: "Dead Stock",
    columns: [
      { key: "sku", header: "SKU", render: (row) => String(row.sku) },
      { key: "description", header: "Description", render: (row) => String(row.description ?? "—") },
      { key: "quantity_on_hand", header: "Quantity on Hand", numeric: true, render: (row) => formatInteger(row.quantity_on_hand as number) },
      { key: "days_since_movement", header: "Days Since Movement", numeric: true, render: (row) => row.days_since_movement !== null ? formatInteger(row.days_since_movement as number) : "—" },
    ],
    getRowId: (row) => String(row.sku),
    csvColumns: ["sku", "description", "quantity_on_hand", "days_since_movement"],
  },
  {
    key: "slow-movers",
    title: "Slow Movers",
    columns: [
      { key: "sku", header: "SKU", render: (row) => String(row.sku) },
      { key: "description", header: "Description", render: (row) => String(row.description ?? "—") },
      { key: "quantity_on_hand", header: "Quantity on Hand", numeric: true, render: (row) => formatInteger(row.quantity_on_hand as number) },
      { key: "units_sold", header: "Units Sold", numeric: true, render: (row) => formatInteger(row.units_sold as number) },
      { key: "avg_daily_demand", header: "Avg Daily Demand", numeric: true, render: (row) => (row.avg_daily_demand as number).toFixed(2) },
    ],
    getRowId: (row) => String(row.sku),
    csvColumns: ["sku", "description", "quantity_on_hand", "units_sold", "avg_daily_demand"],
  },
  {
    key: "valuation",
    title: "Inventory Valuation by Category",
    columns: [
      { key: "category", header: "Category", render: (row) => String(row.category ?? "—") },
      { key: "quantity_on_hand", header: "Quantity on Hand", numeric: true, render: (row) => formatInteger(row.quantity_on_hand as number) },
      { key: "inventory_value", header: "Inventory Value", numeric: true, render: (row) => formatCurrencyPrecise(row.inventory_value as number) },
    ],
    getRowId: (row) => String(row.category ?? "uncategorized"),
    csvColumns: ["category", "quantity_on_hand", "inventory_value"],
  },
  {
    key: "supplier-rollup",
    title: "Supplier Rollup",
    columns: [
      { key: "supplier_id", header: "ID", numeric: true, render: (row) => `#${row.supplier_id}` },
      { key: "name", header: "Supplier", render: (row) => String(row.name) },
      { key: "sku_count", header: "SKU Count", numeric: true, render: (row) => formatInteger(row.sku_count as number) },
      { key: "total_inventory_value", header: "Inventory Value", numeric: true, render: (row) => formatCurrencyPrecise(row.total_inventory_value as number) },
      { key: "open_purchase_order_count", header: "Open POs", numeric: true, render: (row) => formatInteger(row.open_purchase_order_count as number) },
      { key: "on_time_delivery_rate", header: "On-Time Delivery", numeric: true, render: (row) => row.on_time_delivery_rate !== null ? formatPercent((row.on_time_delivery_rate as number) * 100) : "—" },
    ],
    getRowId: (row) => String(row.supplier_id),
    csvColumns: ["supplier_id", "name", "sku_count", "total_inventory_value", "open_purchase_order_count", "on_time_delivery_rate"],
  },
];

function getFetchForReport(key: string) {
  switch (key) {
    case "revenue":
      return () => useRevenue({ groupBy: "month" }).refetch();
    case "profit":
      return () => useProfit({ groupBy: "month" }).refetch();
    case "turnover":
      return () => useTurnover().refetch();
    case "abc":
      return () => useAbc().refetch();
    case "dead-stock":
      return () => useDeadStock().refetch();
    case "slow-movers":
      return () => useSlowMovers().refetch();
    case "valuation":
      return () => useInventoryValuation().refetch();
    case "supplier-rollup":
      return () => useSupplierRollup().refetch();
    default:
      return () => Promise.resolve([]);
  }
}

export function ReportsContent() {
  const [selectedReport, setSelectedReport] = useState<ReportConfig | null>(null);
  const [reportData, setReportData] = useState<Record<string, unknown>[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate(report: ReportConfig) {
    setSelectedReport(report);
    setIsLoading(true);
    setError(null);
    try {
      const fetchFn = getFetchForReport(report.key);
      const data = await fetchFn();
      setReportData(data as Record<string, unknown>[]);
    } catch (err) {
      setError(err instanceof AppError ? err.message : "Could not generate report.");
    } finally {
      setIsLoading(false);
    }
  }

  function handleExport() {
    if (!selectedReport || !reportData.length) return;
    const csv = toCsv(reportData, selectedReport.csvColumns);
    downloadCsv(`${selectedReport.key}-${new Date().toISOString().slice(0, 10)}.csv`, csv);
  }

  return (
    <div className="flex flex-col gap-6 pt-4">
      <h1 className="text-[20px] text-[var(--color-text-hi)]">Reports</h1>
      <p className="text-[13px] text-[var(--color-text-mid)]">
        Generate and export standard reports. Each report queries live data from StockPilot Core.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {REPORTS.map((report) => (
          <button
            key={report.key}
            type="button"
            onClick={() => handleGenerate(report)}
            disabled={isLoading}
            className={`rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4 text-left transition-colors duration-150 hover:border-[var(--color-hairline-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)] ${selectedReport?.key === report.key ? "border-[var(--color-accent)] bg-[var(--color-accent)]/5" : ""} disabled:opacity-40`}
          >
            <h3 className="text-[14px] font-medium text-[var(--color-text-hi)]">{report.title}</h3>
            <p className="mt-1 text-[12px] text-[var(--color-text-mid)]">
              Click to generate and view
            </p>
          </button>
        ))}
      </div>

      {selectedReport && (
        <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-[16px] font-medium text-[var(--color-text-hi)]">{selectedReport.title}</h2>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleExport}
                disabled={isLoading || !reportData.length}
                className="rounded-[6px] border border-[var(--color-hairline)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] transition-colors duration-150 hover:border-[var(--color-hairline-hi)] disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
              >
                Export CSV
              </button>
              <button
                type="button"
                onClick={() => setSelectedReport(null)}
                className="rounded-[6px] border border-[var(--color-hairline)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] transition-colors duration-150 hover:border-[var(--color-hairline-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
              >
                Close
              </button>
            </div>
          </div>

          {isLoading ? (
            <div className="h-32 w-full animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
          ) : error ? (
            <p className="text-[13px] text-[var(--color-danger)]">{error}</p>
          ) : reportData.length === 0 ? (
            <EmptyState
              title="No data"
              description="No data available for this report with the current filters."
            />
          ) : (
            <DataTable
              columns={selectedReport.columns}
              rows={reportData}
              getRowId={selectedReport.getRowId}
              isLoading={isLoading}
            />
          )}
        </div>
      )}
    </div>
  );
}