"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useProduct } from "../../../../hooks/useProduct";
import { useCategories } from "../../../../hooks/useCategories";
import { useBrands } from "../../../../hooks/useBrands";
import { useSupplier } from "../../../../hooks/useSupplier";
import { useProductHistory } from "../../../../hooks/useProductHistory";
import { useDeleteProduct } from "../../../../hooks/useDeleteProduct";
import { useCan } from "../../../../lib/rbac";
import { EmptyState } from "../../../../components/ui/EmptyState";
import { ProvenanceBadge, parseProvenance } from "../../../../components/ui/ProvenanceBadge";
import { formatCurrencyPrecise, formatInteger } from "../../../../lib/format";
import { AppError } from "../../../../lib/api/errors";

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

export function ProductDetailContent({ sku }: { sku: string }) {
  const router = useRouter();
  const product = useProduct(sku);
  const categories = useCategories();
  const brands = useBrands();
  const supplier = useSupplier(product.data?.supplier_id ?? null);
  const history = useProductHistory(sku);
  const deleteProduct = useDeleteProduct();
  const canUpdate = useCan("products:update");
  const canDelete = useCan("products:delete");
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  if (product.isPending) {
    return (
      <div className="flex flex-col gap-3 pt-4" aria-busy="true">
        <div className="h-6 w-48 animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
        <div className="h-32 w-full animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
      </div>
    );
  }

  if (product.isError) {
    if (product.error instanceof AppError && product.error.status === 404) {
      return <EmptyState title="Product not found" description={`No product exists with SKU ${sku}.`} />;
    }
    return (
      <p className="pt-4 text-[13px] text-[var(--color-danger)]">
        {product.error instanceof AppError ? product.error.message : "Could not load this product."}
      </p>
    );
  }

  if (!product.data) {
    return <EmptyState title="Product not found" description={`No product exists with SKU ${sku}.`} />;
  }

  const categoryName = categories.data?.find((c) => c.id === product.data.category_id)?.name;
  const brandName = brands.data?.find((b) => b.id === product.data.brand_id)?.name;

  async function handleDelete() {
    setDeleteError(null);
    try {
      await deleteProduct.mutateAsync(sku);
      router.push("/products");
    } catch (err) {
      setDeleteError(
        err instanceof AppError ? err.message : "Something went wrong. Please try again.",
      );
      setConfirmingDelete(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 pt-4">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-[20px] text-[var(--color-text-hi)]">
            {product.data.description ?? sku}
          </h1>
          <p className="font-mono text-[13px] text-[var(--color-text-mid)]" data-numeric>
            {sku}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {canUpdate && (
            <Link
              href={`/products/${encodeURIComponent(sku)}/edit`}
              className="rounded-[6px] border border-[var(--color-hairline)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] transition-colors duration-150 hover:border-[var(--color-hairline-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
            >
              Edit
            </Link>
          )}
          {canDelete && !confirmingDelete && (
            <button
              type="button"
              onClick={() => setConfirmingDelete(true)}
              className="rounded-[6px] border border-[var(--color-danger)] px-3 py-1.5 text-[13px] text-[var(--color-danger)] transition-colors duration-150 hover:bg-[var(--color-danger)] hover:text-[var(--color-canvas)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
            >
              Delete
            </button>
          )}
          {canDelete && confirmingDelete && (
            <div className="flex items-center gap-2 text-[13px]">
              <span className="text-[var(--color-text-mid)]">Delete this product?</span>
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleteProduct.isPending}
                className="rounded-[6px] bg-[var(--color-danger)] px-3 py-1.5 text-[var(--color-canvas)] disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
              >
                {deleteProduct.isPending ? "Deleting…" : "Confirm"}
              </button>
              <button
                type="button"
                onClick={() => setConfirmingDelete(false)}
                className="rounded-[6px] border border-[var(--color-hairline)] px-3 py-1.5 text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>

      {deleteError && (
        <p role="alert" className="text-[13px] text-[var(--color-danger)]">
          {deleteError}
        </p>
      )}

      <div className="grid grid-cols-2 gap-4 rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4 sm:grid-cols-4">
        <Field
          label="Cost price"
          value={product.data.unit_cost === null ? "—" : formatCurrencyPrecise(product.data.unit_cost)}
          provenance={product.data._provenance.unit_cost}
        />
        <Field
          label="Sale price"
          value={product.data.sale_price === null ? "—" : formatCurrencyPrecise(product.data.sale_price)}
          provenance={product.data._provenance.sale_price}
        />
        <Field
          label="Reorder point"
          value={product.data.reorder_point === null ? "—" : formatInteger(product.data.reorder_point)}
          provenance={product.data._provenance.reorder_point}
        />
        <Field
          label="Safety stock"
          value={product.data.safety_stock === null ? "—" : formatInteger(product.data.safety_stock)}
          provenance={product.data._provenance.safety_stock}
        />
        <Field label="Category" value={categoryName ?? (product.data.category_id ? `#${product.data.category_id}` : "—")} />
        <Field label="Brand" value={brandName ?? (product.data.brand_id ? `#${product.data.brand_id}` : "—")} />
        <Field
          label="On hand"
          value={product.data.quantity_on_hand === null ? "—" : formatInteger(product.data.quantity_on_hand)}
          provenance={product.data._provenance.quantity_on_hand}
        />
      </div>

      <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
        <h2 className="mb-2 text-[16px] font-medium text-[var(--color-text-hi)]">Supplier</h2>
        {product.data.supplier_id === null ? (
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
        <h2 className="mb-2 text-[16px] font-medium text-[var(--color-text-hi)]">History</h2>
        {history.isPending ? (
          <div className="h-16 w-full animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
        ) : history.isError ? (
          <p className="text-[13px] text-[var(--color-danger)]">Could not load history.</p>
        ) : history.data && history.data.length > 0 ? (
          <table className="w-full text-[13px]">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-[0.04em] text-[var(--color-text-mid)]">
                <th className="py-1 pr-3">Field</th>
                <th className="py-1 pr-3">Old value</th>
                <th className="py-1 pr-3">New value</th>
                <th className="py-1">Changed</th>
              </tr>
            </thead>
            <tbody>
              {history.data.map((entry, index) => (
                <tr key={index} className="border-t border-[var(--color-hairline)]">
                  <td className="py-1 pr-3 text-[var(--color-text-hi)]">{entry.field_name}</td>
                  <td className="py-1 pr-3 font-mono text-[var(--color-text-mid)]" data-numeric>
                    {entry.old_value ?? "—"}
                  </td>
                  <td className="py-1 pr-3 font-mono text-[var(--color-text-hi)]" data-numeric>
                    {entry.new_value ?? "—"}
                  </td>
                  <td className="py-1 text-[var(--color-text-mid)]">
                    {new Date(entry.changed_at).toLocaleString("en-GB")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-[13px] text-[var(--color-text-mid)]">No changes recorded yet.</p>
        )}
      </div>

      <p className="text-[13px] text-[var(--color-text-mid)]">
        No image is available — StockPilot Core has not yet chosen an object-storage provider (see{" "}
        <code className="font-mono">docs/BUILD.md</code> Module 2).
      </p>
    </div>
  );
}
