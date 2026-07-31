import { EmptyState } from "../../../components/ui/EmptyState";

// docs/PRODUCT-SPEC.md §24 Forecasts / BUILD.md Stage 7.
export default function ForecastsPage() {
  return (
    <EmptyState
      title="Forecasts"
      description="Demand forecasts with labeled prediction intervals will appear here once Stage 7 wires forecast charts."
    />
  );
}
