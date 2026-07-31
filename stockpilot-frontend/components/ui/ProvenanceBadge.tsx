// docs/DESIGN-SPEC.md §5 "Provenance badges": four states, encoded by
// shape AND text, never hue alone -- all four render in
// --color-text-mid. docs/PRODUCT-SPEC.md §13: every figure sourced from
// RetailOps AI or computed client-side carries one of these; a figure
// with no resolvable source is MISSING SOURCE, not silently plain text.
export type Provenance = "observed" | "derived" | "predicted" | "inferred";

const LABELS: Record<Provenance, string> = {
  observed: "Observed",
  derived: "Derived",
  predicted: "Predicted",
  inferred: "Inferred",
};

function Shape({ provenance }: { provenance: Provenance }) {
  const common = "inline-block h-2 w-2 shrink-0";
  switch (provenance) {
    case "observed":
      return <span className={`${common} rounded-full bg-[var(--color-text-mid)]`} aria-hidden="true" />;
    case "derived":
      return (
        <span
          className={`${common} rounded-full border border-[var(--color-text-mid)]`}
          aria-hidden="true"
        />
      );
    case "predicted":
      return (
        <span className={`${common} relative`} aria-hidden="true">
          <span className="absolute inset-0 rounded-full border border-[var(--color-text-mid)]" />
          <span className="absolute left-0 right-0 top-1/2 h-px -translate-y-1/2 bg-[var(--color-text-mid)]" />
        </span>
      );
    case "inferred":
      return (
        <span
          className={`${common} rounded-full border border-dashed border-[var(--color-text-mid)]`}
          aria-hidden="true"
        />
      );
  }
}

export function ProvenanceBadge({ provenance }: { provenance: Provenance }) {
  return (
    <span className="inline-flex items-center gap-1 text-[11px] text-[var(--color-text-mid)]">
      <Shape provenance={provenance} />
      {LABELS[provenance]}
    </span>
  );
}

export function MissingSourceBadge() {
  return (
    <span className="text-[11px] uppercase tracking-[0.04em] text-[var(--color-danger)]">
      Missing source
    </span>
  );
}

/** Narrows an arbitrary provenance string from the API into the four known values, defaulting unrecognized values to nothing renderable. */
export function parseProvenance(value: string | undefined): Provenance | null {
  if (value === "observed" || value === "derived" || value === "predicted" || value === "inferred") {
    return value;
  }
  return null;
}
