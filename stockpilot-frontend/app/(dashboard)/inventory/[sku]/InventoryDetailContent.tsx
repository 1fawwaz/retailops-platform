"use client";

import { useProduct } from "../../../../hooks/useProduct";
import { useStockItem } from "../../../../hooks/useStockItem";
import { useSupplier } from "../../../../hooks/useSupplier";
import { useForecast } from "../../../../hooks/useForecast";
import { EmptyState } from "../../../../components/ui/EmptyState";
import { ProvenanceBadge, parseProvenance } from "../../../../components/ui/ProvenanceBadge";
import { formatCurrency, formatInteger } from "../../../../lib/format";
import { AppError } from "../../../../lib/api/errors";

const FORECAST_HORIZON_DAYS = 14;

function Field({ label, value, provenance }: { label: string; value: string; provenance?: string }) {
  const parsed = parseProvenance(provenance);
  return (
    <div>
      <div className="text-[13px] text-[var(--color-text-mid)]">{label}</div>
      <div className="font-mono text-[14px] text-[var(--color-text-hi)]" data-numeric>
        {value}
      </div>
      {parsed && <ProvenanceBadge provenance={parsed} />}
    </div>
  );
}

export function InventoryDetailContent({ sku }: { sku: string }) {
  const product = useProduct(sku);
  const stockItem = useStockItem(sku);
  const supplierId = product.data?.supplier_id ?? null;
  const supplier = useSupplier(supplierId);
  const forecast = useForecast(sku, FORECAST_HORIZON_DAYS);

  if (product.isPending || stockItem.isPending) {
    return (
      <div className="flex flex-col gap-3 pt-4" aria-busy="true">
        <div className="h-6 w-48 animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
        <div className="h-32 w-full animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
      </div>
    );
  }

  // A 404 means "no such SKU" -- a genuinely-empty result, per
  // docs/PRODUCT-SPEC.md §18, not a system error. Every other failure
  // (network, 500, etc.) still renders as an error.
  if (product.isError) {
    if (product.error instanceof AppError && product.error.status === 404) {
      return (
        <EmptyState title="Product not found" description={`No product exists with SKU ${sku}.`} />
      );
    }
    return (
      <p className="pt-4 text-[13px] text-[var(--color-danger)]">
        {product.error instanceof AppError ? product.error.message : "Could not load this product."}
      </p>
    );
  }

  if (!product.data) {
    return (
      <EmptyState title="Product not found" description={`No product exists with SKU ${sku}.`} />
    );
  }

  return (
    <div className="flex flex-col gap-6 pt-4">
      <div>
        <h1 className="text-[20px] text-[var(--color-text-hi)]">{product.data.description ?? sku}</h1>
        <p className="font-mono text-[13px] text-[var(--color-text-mid)]" data-numeric>
          {sku}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4 sm:grid-cols-4">
        <Field
          label="On hand"
          value={stockItem.data ? formatInteger(stockItem.data.quantity_on_hand) : "—"}
          provenance={stockItem.data?._provenance.quantity_on_hand}
        />
        <Field
          label="Reorder point"
          value={product.data.reorder_point === null ? "—" : formatInteger(product.data.reorder_point)}
          provenance={product.data._provenance.reorder_point}
        />
        <Field
          label="Cost price"
          value={product.data.unit_cost === null ? "—" : formatCurrency(product.data.unit_cost)}
          provenance={product.data._provenance.unit_cost}
        />
        <Field label="Category" value={product.data.category_id ? `#${product.data.category_id}` : "—"} />
      </div>

      <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
        <h2 className="mb-2 text-[16px] font-medium text-[var(--color-text-hi)]">Supplier</h2>
        {supplierId === null ? (
          <p className="text-[13px] text-[var(--color-text-mid)]">No supplier linked.</p>
        ) : supplier.isPending ? (
          <div className="h-5 w-40 animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
        ) : supplier.isError ? (
          <p className="text-[13px] text-[var(--color-danger)]">Could not load supplier.</p>
        ) : (
          <p className="text-[13px] text-[var(--color-text-hi)]">
            {supplier.data?.name} — {supplier.data?.lead_time_days}-day lead time
          </p>
        )}
      </div>

      <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
        <h2 className="mb-2 text-[16px] font-medium text-[var(--color-text-hi)]">
          Forecast ({FORECAST_HORIZON_DAYS}-day horizon)
        </h2>
        {forecast.isPending ? (
          <div className="h-5 w-56 animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
        ) : forecast.isError ? (
          <p className="text-[13px] text-[var(--color-danger)]">Could not load forecast.</p>
        ) : !forecast.data ? (
          <p className="text-[13px] text-[var(--color-text-mid)]">No forecast available for this SKU.</p>
        ) : (
          <div className="flex items-center gap-3">
            <span className="font-mono text-[14px] text-[var(--color-text-hi)]" data-numeric>
              {forecast.data.predicted_daily_demand.toFixed(1)} units/day
            </span>
            <span className="font-mono text-[13px] text-[var(--color-text-mid)]" data-numeric>
              (80% interval: {forecast.data.confidence_interval_lower.toFixed(1)}–
              {forecast.data.confidence_interval_upper.toFixed(1)})
            </span>
            <ProvenanceBadge provenance="predicted" />
          </div>
        )}
      </div>
    </div>
  );
}
