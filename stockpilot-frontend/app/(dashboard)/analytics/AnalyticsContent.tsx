"use client";

import { useState } from "react";
import { useRevenue, useProfit, useTurnover, useAbc, useTopProducts, useBottomProducts, usePeriodComparison, useSupplierRollup, usePurchaseOrderKpis, useDeadStock, useSlowMovers, useInventoryValuation } from "../../../hooks/useAnalytics";
import { DataTable, type DataTableColumn } from "../../../components/data-table/DataTable";
import { EmptyState } from "../../../components/ui/EmptyState";
import { formatCurrencyPrecise, formatInteger, formatPercent } from "../../../lib/format";
import { AppError } from "../../../lib/api/errors";

type MetricCardProps = {
  title: string;
  value: string;
  subValue?: string;
  trend?: "up" | "down" | "neutral";
};

function MetricCard({ title, value, subValue, trend }: MetricCardProps) {
  return (
    <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
      <div className="text-[13px] text-[var(--color-text-mid)]">{title}</div>
      <div className="font-mono text-[24px] text-[var(--color-text-hi)]" data-numeric>{value}</div>
      {subValue && (
        <div className={`text-[12px] font-mono ${trend === "up" ? "text-[var(--color-success)]" : trend === "down" ? "text-[var(--color-danger)]" : "text-[var(--color-text-mid)]"}`} data-numeric>
          {subValue}
        </div>
      )}
    </div>
  );
}

export function AnalyticsContent() {
  const [groupBy, setGroupBy] = useState<"day" | "week" | "month" | "category">("month");
  const [dateRange, setDateRange] = useState({ start: "", end: "" });

  const revenue = useRevenue({ groupBy, startDate: dateRange.start || undefined, endDate: dateRange.end || undefined });
  const profit = useProfit({ groupBy, startDate: dateRange.start || undefined, endDate: dateRange.end || undefined });
  const turnover = useTurnover();
  const abc = useAbc();
  const topProducts = useTopProducts(10);
  const bottomProducts = useBottomProducts(10);
  const periodComparison = usePeriodComparison({ startDate: dateRange.start || undefined, endDate: dateRange.end || undefined });
  const supplierRollup = useSupplierRollup();
  const poKpis = usePurchaseOrderKpis();
  const deadStock = useDeadStock();
  const slowMovers = useSlowMovers();
  const inventoryValuation = useInventoryValuation();

  const isLoading = revenue.isPending || profit.isPending || turnover.isPending || abc.isPending || topProducts.isPending || bottomProducts.isPending || supplierRollup.isPending || poKpis.isPending || deadStock.isPending || slowMovers.isPending || inventoryValuation.isPending;

  const isError = revenue.isError || profit.isError || turnover.isError || abc.isError || topProducts.isError || bottomProducts.isError || supplierRollup.isError || poKpis.isError || deadStock.isError || slowMovers.isError || inventoryValuation.isError;

  const error = revenue.error || profit.error || turnover.error || abc.error || topProducts.error || bottomProducts.error || supplierRollup.error || poKpis.error || deadStock.error || slowMovers.error || inventoryValuation.error;

  function handleGroupByChange(event: React.ChangeEvent<HTMLSelectElement>) {
    setGroupBy(event.target.value as "day" | "week" | "month" | "category");
  }

  function handleDateRangeSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    setDateRange({
      start: formData.get("startDate") as string,
      end: formData.get("endDate") as string,
    });
  }

  if (isError) {
    return (
      <p className="text-[13px] text-[var(--color-danger)]">
        {error instanceof AppError ? error.message : "Could not load analytics."}
      </p>
    );
  }

  const totalRevenue = revenue.data?.reduce((sum, p) => sum + p.revenue, 0) ?? 0;
  const totalProfit = profit.data?.reduce((sum, p) => sum + p.profit, 0) ?? 0;
  const avgMargin = totalRevenue > 0 ? (totalProfit / totalRevenue) * 100 : 0;
  const totalInventoryValue = inventoryValuation.data?.total_inventory_value ?? 0;
  const openPOCount = poKpis.data?.open_purchase_order_count ?? 0;

  return (
    <div className="flex flex-col gap-6 pt-4">
      <div className="flex flex-wrap items-end gap-3">
        <form onSubmit={handleDateRangeSubmit} className="flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="startDate" className="mb-1 block text-[13px] text-[var(--color-text-mid)]">
              Start Date
            </label>
            <input
              id="startDate"
              name="startDate"
              type="date"
              value={dateRange.start}
              onChange={() => {}}
              className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-canvas)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
            />
          </div>
          <div>
            <label htmlFor="endDate" className="mb-1 block text-[13px] text-[var(--color-text-mid)]">
              End Date
            </label>
            <input
              id="endDate"
              name="endDate"
              type="date"
              value={dateRange.end}
              onChange={() => {}}
              className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-canvas)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
            />
          </div>
          <div>
            <label htmlFor="groupBy" className="mb-1 block text-[13px] text-[var(--color-text-mid)]">
              Group By
            </label>
            <select
              id="groupBy"
              value={groupBy}
              onChange={handleGroupByChange}
              className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-canvas)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
            >
              <option value="day">Day</option>
              <option value="week">Week</option>
              <option value="month">Month</option>
              <option value="category">Category</option>
            </select>
          </div>
          <button
            type="submit"
            className="rounded-[6px] border border-[var(--color-hairline)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] transition-colors duration-150 hover:border-[var(--color-hairline-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
          >
            Apply
          </button>
        </form>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" aria-busy="true">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4 animate-pulse">
              <div className="h-4 w-24 bg-[var(--color-raised)] rounded mb-2" />
              <div className="h-8 w-32 bg-[var(--color-raised)] rounded" />
            </div>
          ))}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard title="Total Revenue" value={formatCurrencyPrecise(totalRevenue)} />
            <MetricCard title="Total Profit" value={formatCurrencyPrecise(totalProfit)} subValue={`${avgMargin.toFixed(1)}% margin`} trend={avgMargin >= 0 ? "up" : "down"} />
            <MetricCard title="Inventory Value" value={formatCurrencyPrecise(totalInventoryValue)} />
            <MetricCard title="Open POs" value={String(openPOCount)} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
              <h3 className="mb-4 text-[16px] font-medium text-[var(--color-text-hi)]">Revenue by {groupBy.charAt(0).toUpperCase() + groupBy.slice(1)}</h3>
              {revenue.data && revenue.data.length > 0 ? (
                <DataTable
                  columns={[
                    { key: "period", header: groupBy.charAt(0).toUpperCase() + groupBy.slice(1), render: (row) => row.period },
                    { key: "revenue", header: "Revenue", numeric: true, render: (row) => formatCurrencyPrecise(row.revenue) },
                    { key: "units", header: "Units", numeric: true, render: (row) => formatInteger(row.units) },
                  ]}
                  rows={revenue.data}
                  getRowId={(row) => row.period}
                  isLoading={revenue.isPending}
                />
              ) : (
                <p className="text-[13px] text-[var(--color-text-mid)]">No revenue data for this period.</p>
              )}
            </div>

            <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
              <h3 className="mb-4 text-[16px] font-medium text-[var(--color-text-hi)]">Profit by {groupBy.charAt(0).toUpperCase() + groupBy.slice(1)}</h3>
              {profit.data && profit.data.length > 0 ? (
                <DataTable
                  columns={[
                    { key: "period", header: groupBy.charAt(0).toUpperCase() + groupBy.slice(1), render: (row) => row.period },
                    { key: "profit", header: "Profit", numeric: true, render: (row) => formatCurrencyPrecise(row.profit) },
                    { key: "margin_pct", header: "Margin %", numeric: true, render: (row) => formatPercent(row.margin_pct) },
                  ]}
                  rows={profit.data}
                  getRowId={(row) => row.period}
                  isLoading={profit.isPending}
                />
              ) : (
                <p className="text-[13px] text-[var(--color-text-mid)]">No profit data for this period.</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
              <h3 className="mb-4 text-[16px] font-medium text-[var(--color-text-hi)]">ABC Classification</h3>
              {abc.data && abc.data.length > 0 ? (
                <DataTable
                  columns={[
                    { key: "sku", header: "SKU", render: (row) => <span data-numeric className="font-mono">{row.sku}</span> },
                    { key: "revenue", header: "Revenue", numeric: true, render: (row) => formatCurrencyPrecise(row.revenue) },
                    { key: "cumulative_pct", header: "Cumulative %", numeric: true, render: (row) => formatPercent(row.cumulative_pct * 100) },
                    { key: "abc_class", header: "Class", render: (row) => <span className="font-medium">{row.abc_class}</span> },
                  ]}
                  rows={abc.data}
                  getRowId={(row) => row.sku}
                  isLoading={abc.isPending}
                />
              ) : (
                <p className="text-[13px] text-[var(--color-text-mid)]">No ABC data available.</p>
              )}
            </div>

            <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
              <h3 className="mb-4 text-[16px] font-medium text-[var(--color-text-hi)]">Turnover Ratio</h3>
              {turnover.data && turnover.data.length > 0 ? (
                <DataTable
                  columns={[
                    { key: "sku", header: "SKU", render: (row) => <span data-numeric className="font-mono">{row.sku}</span> },
                    { key: "description", header: "Description", render: (row) => row.description ?? "—" },
                    { key: "turnover_ratio", header: "Turnover", numeric: true, render: (row) => row.turnover_ratio.toFixed(2) },
                    { key: "avg_stock_on_hand", header: "Avg Stock", numeric: true, render: (row) => formatInteger(row.avg_stock_on_hand) },
                  ]}
                  rows={turnover.data}
                  getRowId={(row) => row.sku}
                  isLoading={turnover.isPending}
                />
              ) : (
                <p className="text-[13px] text-[var(--color-text-mid)]">No turnover data available.</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
              <h3 className="mb-4 text-[16px] font-medium text-[var(--color-text-hi)]">Top 10 Products by Revenue</h3>
              {topProducts.data && topProducts.data.length > 0 ? (
                <DataTable
                  columns={[
                    { key: "sku", header: "SKU", render: (row) => <span data-numeric className="font-mono">{row.sku}</span> },
                    { key: "description", header: "Description", render: (row) => row.description ?? "—" },
                    { key: "units", header: "Units", numeric: true, render: (row) => formatInteger(row.units) },
                    { key: "revenue", header: "Revenue", numeric: true, render: (row) => formatCurrencyPrecise(row.revenue) },
                    { key: "margin_pct", header: "Margin %", numeric: true, render: (row) => row.margin_pct !== null ? formatPercent(row.margin_pct) : "—" },
                  ]}
                  rows={topProducts.data}
                  getRowId={(row) => row.sku}
                  isLoading={topProducts.isPending}
                />
              ) : (
                <p className="text-[13px] text-[var(--color-text-mid)]">No top products data.</p>
              )}
            </div>

            <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
              <h3 className="mb-4 text-[16px] font-medium text-[var(--color-text-hi)]">Bottom 10 Products by Revenue</h3>
              {bottomProducts.data && bottomProducts.data.length > 0 ? (
                <DataTable
                  columns={[
                    { key: "sku", header: "SKU", render: (row) => <span data-numeric className="font-mono">{row.sku}</span> },
                    { key: "description", header: "Description", render: (row) => row.description ?? "—" },
                    { key: "units", header: "Units", numeric: true, render: (row) => formatInteger(row.units) },
                    { key: "revenue", header: "Revenue", numeric: true, render: (row) => formatCurrencyPrecise(row.revenue) },
                  ]}
                  rows={bottomProducts.data}
                  getRowId={(row) => row.sku}
                  isLoading={bottomProducts.isPending}
                />
              ) : (
                <p className="text-[13px] text-[var(--color-text-mid)]">No bottom products data.</p>
              )}
            </div>
          </div>

          <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
            <h3 className="mb-4 text-[16px] font-medium text-[var(--color-text-hi)]">Period Comparison</h3>
            {periodComparison.data && periodComparison.data.length > 0 ? (
              <DataTable
                columns={[
                  { key: "metric", header: "Metric", render: (row) => row.metric },
                  { key: "current", header: "Current", numeric: true, render: (row) => formatCurrencyPrecise(row.current) },
                  { key: "prior", header: "Prior", numeric: true, render: (row) => formatCurrencyPrecise(row.prior) },
                  { key: "change_pct", header: "Change %", numeric: true, render: (row) => formatPercent(row.change_pct) },
                ]}
                rows={periodComparison.data}
                getRowId={(row) => row.metric}
                isLoading={periodComparison.isPending}
              />
            ) : (
              <p className="text-[13px] text-[var(--color-text-mid)]">No period comparison data.</p>
            )}
          </div>

          <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
            <h3 className="mb-4 text-[16px] font-medium text-[var(--color-text-hi)]">Supplier Rollup</h3>
            {supplierRollup.data && supplierRollup.data.length > 0 ? (
              <DataTable
                columns={[
                  { key: "supplier_id", header: "ID", numeric: true, render: (row) => <span data-numeric className="font-mono">#{row.supplier_id}</span> },
                  { key: "name", header: "Supplier", render: (row) => row.name },
                  { key: "sku_count", header: "SKUs", numeric: true, render: (row) => formatInteger(row.sku_count) },
                  { key: "total_inventory_value", header: "Inventory Value", numeric: true, render: (row) => formatCurrencyPrecise(row.total_inventory_value) },
                  { key: "open_purchase_order_count", header: "Open POs", numeric: true, render: (row) => formatInteger(row.open_purchase_order_count) },
                  { key: "on_time_delivery_rate", header: "On-Time Delivery", numeric: true, render: (row) => row.on_time_delivery_rate !== null ? formatPercent(row.on_time_delivery_rate * 100) : "—" },
                ]}
                rows={supplierRollup.data}
                getRowId={(row) => row.supplier_id}
                isLoading={supplierRollup.isPending}
              />
            ) : (
              <p className="text-[13px] text-[var(--color-text-mid)]">No supplier data.</p>
            )}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
              <h3 className="mb-4 text-[16px] font-medium text-[var(--color-text-hi)]">Dead Stock</h3>
              {deadStock.data && deadStock.data.length > 0 ? (
                <DataTable
                  columns={[
                    { key: "sku", header: "SKU", render: (row) => <span data-numeric className="font-mono">{row.sku}</span> },
                    { key: "description", header: "Description", render: (row) => row.description ?? "—" },
                    { key: "quantity_on_hand", header: "On Hand", numeric: true, render: (row) => formatInteger(row.quantity_on_hand) },
                    { key: "days_since_movement", header: "Days Since Movement", numeric: true, render: (row) => row.days_since_movement !== null ? formatInteger(row.days_since_movement) : "—" },
                  ]}
                  rows={deadStock.data}
                  getRowId={(row) => row.sku}
                  isLoading={deadStock.isPending}
                />
              ) : (
                <p className="text-[13px] text-[var(--color-text-mid)]">No dead stock.</p>
              )}
            </div>

            <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
              <h3 className="mb-4 text-[16px] font-medium text-[var(--color-text-hi)]">Slow Movers</h3>
              {slowMovers.data && slowMovers.data.length > 0 ? (
                <DataTable
                  columns={[
                    { key: "sku", header: "SKU", render: (row) => <span data-numeric className="font-mono">{row.sku}</span> },
                    { key: "description", header: "Description", render: (row) => row.description ?? "—" },
                    { key: "quantity_on_hand", header: "On Hand", numeric: true, render: (row) => formatInteger(row.quantity_on_hand) },
                    { key: "units_sold", header: "Units Sold", numeric: true, render: (row) => formatInteger(row.units_sold) },
                    { key: "avg_daily_demand", header: "Avg Daily Demand", numeric: true, render: (row) => row.avg_daily_demand.toFixed(2) },
                  ]}
                  rows={slowMovers.data}
                  getRowId={(row) => row.sku}
                  isLoading={slowMovers.isPending}
                />
              ) : (
                <p className="text-[13px] text-[var(--color-text-mid)]">No slow movers.</p>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}