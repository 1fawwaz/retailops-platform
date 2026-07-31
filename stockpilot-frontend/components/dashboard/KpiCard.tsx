import { ProvenanceBadge, type Provenance } from "../ui/ProvenanceBadge";

// docs/DESIGN-SPEC.md §4: dashboard hero figures render 40px mono,
// weight 500, tabular-nums. docs/PRODUCT-SPEC.md §11: every KPI is
// provenance-labeled per §13.
export interface KpiCardProps {
  label: string;
  value: string;
  provenance: Provenance;
  note?: string;
}

export function KpiCard({ label, value, provenance, note }: KpiCardProps) {
  return (
    <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
      <div className="mb-2 text-[13px] text-[var(--color-text-mid)]">{label}</div>
      <div className="font-mono text-[28px] font-medium text-[var(--color-text-hi)]" data-numeric>
        {value}
      </div>
      <div className="mt-2 flex items-center justify-between">
        <ProvenanceBadge provenance={provenance} />
        {note && <span className="text-[11px] text-[var(--color-text-low)]">{note}</span>}
      </div>
    </div>
  );
}

export function KpiCardSkeleton() {
  return (
    <div
      className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4"
      aria-busy="true"
    >
      <div className="mb-3 h-3 w-24 animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
      <div className="h-7 w-32 animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
    </div>
  );
}

export function KpiCardError({ label, message }: { label: string; message: string }) {
  return (
    <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
      <div className="mb-2 text-[13px] text-[var(--color-text-mid)]">{label}</div>
      <p className="text-[13px] text-[var(--color-danger)]">{message}</p>
    </div>
  );
}
