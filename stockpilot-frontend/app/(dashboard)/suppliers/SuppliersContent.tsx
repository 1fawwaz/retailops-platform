"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useSuppliers } from "../../../hooks/useSuppliers";
import { DataTable, type DataTableColumn } from "../../../components/data-table/DataTable";
import { EmptyState } from "../../../components/ui/EmptyState";
import { useCan } from "../../../lib/rbac";
import type { SupplierListItem } from "../../../lib/validation/suppliers";
import { AppError } from "../../../lib/api/errors";

const columns: DataTableColumn<SupplierListItem>[] = [
  { key: "name", header: "Name", render: (row) => row.name },
  {
    key: "lead_time_days",
    header: "Lead time",
    numeric: true,
    render: (row) => `${row.lead_time_days}d`,
  },
  {
    key: "reliability_score",
    header: "Reliability",
    numeric: true,
    render: (row) => row.reliability_score.toFixed(2),
  },
];

export function SuppliersContent() {
  const router = useRouter();
  const canCreate = useCan("suppliers:create");
  const { data, isPending, isError, error } = useSuppliers();

  return (
    <div className="flex flex-col gap-4 pt-4">
      <div className="flex items-center justify-end">
        {canCreate && (
          <Link
            href="/suppliers/new"
            className="rounded-[6px] bg-[var(--color-accent)] px-3 py-1.5 text-[13px] text-[var(--color-canvas)] transition-colors duration-150 hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
          >
            New supplier
          </Link>
        )}
      </div>

      {isError ? (
        <p className="text-[13px] text-[var(--color-danger)]">
          {error instanceof AppError ? error.message : "Could not load suppliers."}
        </p>
      ) : (
        <DataTable
          columns={columns}
          rows={data ?? []}
          getRowId={(row) => row.id}
          isLoading={isPending}
          onRowClick={(row) => router.push(`/suppliers/${row.id}`)}
          emptyState={
            <EmptyState
              title="No suppliers yet"
              description="Add your first supplier to start tracking vendor relationships."
              action={
                canCreate ? (
                  <Link
                    href="/suppliers/new"
                    className="rounded-[6px] bg-[var(--color-accent)] px-3 py-1.5 text-[13px] text-[var(--color-canvas)] hover:opacity-90"
                  >
                    Add your first supplier
                  </Link>
                ) : undefined
              }
            />
          }
        />
      )}
    </div>
  );
}
