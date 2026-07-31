// docs/ARCHITECTURE.md §9 / docs/DESIGN-SPEC.md §6: skeleton blocks
// matching final layout dimensions, never a bare spinner. Stage 0's
// pages are all empty-state (no data fetch yet), so this mostly covers
// future stages' route-level Suspense fallback -- present now so the
// pattern exists before Stage 1 needs it for real.
export default function DashboardSegmentLoading() {
  return (
    <div className="flex flex-col gap-3 p-4" aria-busy="true" aria-label="Loading">
      <div className="h-6 w-40 animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
      <div className="h-24 w-full animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
      <div className="h-24 w-full animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
    </div>
  );
}
