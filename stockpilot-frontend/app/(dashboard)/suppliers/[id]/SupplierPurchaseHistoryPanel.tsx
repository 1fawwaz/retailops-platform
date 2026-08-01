"use client";

import { useSupplierPurchaseOrders } from "../../../../hooks/useSupplierPurchaseOrders";

export function SupplierPurchaseHistoryPanel({ supplierId }: { supplierId: number }) {
  const purchaseOrders = useSupplierPurchaseOrders(supplierId);

  return (
    <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
      <h2 className="mb-2 text-[16px] font-medium text-[var(--color-text-hi)]">Purchase history</h2>
      {purchaseOrders.isPending ? (
        <div className="h-16 w-full animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
      ) : purchaseOrders.isError ? (
        <p className="text-[13px] text-[var(--color-danger)]">Could not load purchase history.</p>
      ) : purchaseOrders.data && purchaseOrders.data.length > 0 ? (
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-[0.04em] text-[var(--color-text-mid)]">
              <th className="py-1 pr-3">PO</th>
              <th className="py-1 pr-3">Status</th>
              <th className="py-1 pr-3">Lines</th>
              <th className="py-1">Created</th>
            </tr>
          </thead>
          <tbody>
            {purchaseOrders.data.map((po) => (
              <tr key={po.id} className="border-t border-[var(--color-hairline)]">
                <td className="py-1 pr-3 font-mono text-[var(--color-text-hi)]" data-numeric>
                  #{po.id}
                </td>
                <td className="py-1 pr-3 text-[var(--color-text-hi)]">{po.status}</td>
                <td className="py-1 pr-3 font-mono text-[var(--color-text-mid)]" data-numeric>
                  {po.lines.length}
                </td>
                <td className="py-1 text-[var(--color-text-mid)]">
                  {new Date(po.created_at).toLocaleDateString("en-GB")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="text-[13px] text-[var(--color-text-mid)]">No purchase orders yet.</p>
      )}
      <p className="mt-3 text-[13px] text-[var(--color-text-mid)]">
        Creating a new purchase order from this supplier isn&apos;t available yet — the Purchase
        Orders workflow hasn&apos;t been built.
      </p>
    </div>
  );
}
