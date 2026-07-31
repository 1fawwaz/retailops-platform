"use client";

// docs/DESIGN-SPEC.md §5 Tables: 13px rows, 32px row height, hairline
// row separators, no zebra striping, no vertical grid lines. Header row:
// 11px uppercase, --color-text-mid, letter-spacing 0.04em, sticky.
// Numbers right-aligned and monospaced.
//
// docs/CLAUDE.md §6: "a new resource's table... is built by passing
// column/field config into the shared primitive, not by copy-pasting a
// table component per resource." Sort/pagination state is controlled by
// the caller (server-side pagination per BUILD.md Stage 2's own
// requirement) -- this component never fetches or owns page/sort state
// itself, only renders it and reports interaction back up.

export type SortDirection = "asc" | "desc";

export interface DataTableColumn<T> {
  key: string;
  header: string;
  /** Numeric columns are right-aligned and monospaced per DESIGN-SPEC §5. */
  numeric?: boolean;
  sortable?: boolean;
  render: (row: T) => React.ReactNode;
}

export interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  rows: T[];
  getRowId: (row: T) => string | number;
  sortKey?: string;
  sortDirection?: SortDirection;
  onSortChange?: (key: string) => void;
  emptyState?: React.ReactNode;
  isLoading?: boolean;
  onRowClick?: (row: T) => void;
}

export function DataTable<T>({
  columns,
  rows,
  getRowId,
  sortKey,
  sortDirection,
  onSortChange,
  emptyState,
  isLoading,
  onRowClick,
}: DataTableProps<T>) {
  if (!isLoading && rows.length === 0 && emptyState) {
    return <>{emptyState}</>;
  }

  return (
    <div className="overflow-x-auto rounded-[6px] border border-[var(--color-hairline)]">
      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr className="sticky top-0 bg-[var(--color-surface)]">
            {columns.map((column) => {
              const isSorted = sortKey === column.key;
              return (
                <th
                  key={column.key}
                  scope="col"
                  aria-sort={
                    isSorted ? (sortDirection === "asc" ? "ascending" : "descending") : undefined
                  }
                  className={`h-8 border-b border-[var(--color-hairline)] px-3 text-[11px] uppercase tracking-[0.04em] text-[var(--color-text-mid)] ${
                    column.numeric ? "text-right" : "text-left"
                  }`}
                >
                  {column.sortable && onSortChange ? (
                    <button
                      type="button"
                      onClick={() => onSortChange(column.key)}
                      className="uppercase tracking-[0.04em] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
                    >
                      {column.header}
                      {isSorted ? (sortDirection === "asc" ? " ▲" : " ▼") : ""}
                    </button>
                  ) : (
                    column.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={getRowId(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={`h-8 border-b border-[var(--color-hairline)] last:border-b-0 ${
                onRowClick ? "cursor-pointer hover:bg-[var(--color-raised)]" : ""
              }`}
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={`px-3 text-[var(--color-text-hi)] ${
                    column.numeric ? "text-right font-mono" : "text-left"
                  }`}
                  data-numeric={column.numeric || undefined}
                >
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
