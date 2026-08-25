import { Suspense } from "react";
import { ForecastsContent } from "./ForecastsContent";

// docs/PRODUCT-SPEC.md §24 Forecasts / BUILD.md Stage 7.
// Wired to real POST /forecast/demand endpoint.
export default function ForecastsPage() {
  return (
    <Suspense fallback={null}>
      <ForecastsContent />
    </Suspense>
  );
}