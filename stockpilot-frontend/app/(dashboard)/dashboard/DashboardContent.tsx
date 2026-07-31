"use client";

import { useRevenue } from "../../../hooks/useRevenue";
import { useInventoryValuation } from "../../../hooks/useInventoryValuation";
import { useLowStockCount } from "../../../hooks/useLowStockCount";
import { KpiCard, KpiCardError, KpiCardSkeleton } from "../../../components/dashboard/KpiCard";
import { TimeSeriesChart } from "../../../components/charts/TimeSeriesChart";
import { formatCurrency, formatInteger, formatPercentChange } from "../../../lib/format";
import { AppError } from "../../../lib/api/errors";

function errorMessage(error: unknown): string {
  return error instanceof AppError ? error.message : "Could not load this figure.";
}

function RevenueCard() {
  // group_by=month with no date range returns the full monthly series --
  // the last two entries are "this month" / "the month before," used
  // both for the KPI card's period-over-period delta and the chart
  // below. This % change is computed here (client-side), not returned
  // by the API, so it's labeled 'derived', same as the two revenue
  // figures it's computed from (docs/PRODUCT-SPEC.md §13).
  const { data, isPending, isError, error } = useRevenue({ groupBy: "month" });

  if (isPending) return <KpiCardSkeleton />;
  if (isError) return <KpiCardError label="Revenue" message={errorMessage(error)} />;
  if (data.length === 0) {
    return <KpiCardError label="Revenue" message="No revenue data available yet." />;
  }

  const latest = data[data.length - 1];
  const previous = data.length > 1 ? data[data.length - 2] : null;
  const change = previous ? formatPercentChange(latest.revenue, previous.revenue) : null;

  return (
    <KpiCard
      label={`Revenue (${latest.period})`}
      value={formatCurrency(latest.revenue)}
      provenance="derived"
      note={change ? `${change} vs. prior month` : undefined}
    />
  );
}

function InventoryValueCard() {
  const { data, isPending, isError, error } = useInventoryValuation();

  if (isPending) return <KpiCardSkeleton />;
  if (isError) return <KpiCardError label="Inventory value" message={errorMessage(error)} />;

  return (
    <KpiCard
      label="Inventory value"
      value={formatCurrency(data.total_inventory_value)}
      provenance="derived"
    />
  );
}

function LowStockCard() {
  const { data, isPending, isError, error } = useLowStockCount();

  if (isPending) return <KpiCardSkeleton />;
  if (isError) return <KpiCardError label="Low-stock items" message={errorMessage(error)} />;

  return (
    <KpiCard
      label="Low-stock items"
      value={data.isLowerBound ? `${formatInteger(data.count)}+` : formatInteger(data.count)}
      provenance="derived"
      note={data.isLowerBound ? "capped at API page limit" : undefined}
    />
  );
}

function RevenueChart() {
  const { data, isPending, isError } = useRevenue({ groupBy: "month" });

  if (isPending) {
    return <div className="h-[240px] animate-pulse rounded-[6px] bg-[var(--color-raised)]" />;
  }
  if (isError || data.length === 0) {
    return (
      <p className="flex h-[240px] items-center justify-center text-[13px] text-[var(--color-text-mid)]">
        Revenue chart unavailable.
      </p>
    );
  }

  return (
    <TimeSeriesChart
      data={data.map((period) => ({ label: period.period, value: period.revenue }))}
    />
  );
}

export function DashboardContent() {
  return (
    <div className="flex flex-col gap-6 pt-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <RevenueCard />
        <InventoryValueCard />
        <LowStockCard />
      </div>

      <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
        <h2 className="mb-3 text-[16px] font-medium text-[var(--color-text-hi)]">
          Revenue by month
        </h2>
        <RevenueChart />
      </div>

      {/* docs/stockpilot-gaps.md #4: StockPilot Core has no Purchase
          Orders or Sales/Orders API, so "Open PO count" and the
          activity feed (docs/PRODUCT-SPEC.md §11/FR-2) have no real
          data source. Disclosed here, not silently dropped, per
          PRODUCT-SPEC.md §23 ("no feature silently absent"). */}
      <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
        <h2 className="mb-1 text-[16px] font-medium text-[var(--color-text-hi)]">
          Open purchase orders &amp; recent activity
        </h2>
        <p className="text-[13px] text-[var(--color-text-mid)]">
          Not available yet — StockPilot Core has no Purchase Orders or Sales API to source this
          from. See <code className="font-mono">docs/stockpilot-gaps.md</code> #4.
        </p>
      </div>
    </div>
  );
}
