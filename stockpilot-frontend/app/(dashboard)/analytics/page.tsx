import { EmptyState } from "../../../components/ui/EmptyState";

// docs/PRODUCT-SPEC.md §24 Analytics / BUILD.md Stage 8.
export default function AnalyticsPage() {
  return (
    <EmptyState
      title="Analytics"
      description="Turnover, ABC classification, dead stock, and supplier analytics will appear here once Stage 8 wires the executive rollup."
    />
  );
}
