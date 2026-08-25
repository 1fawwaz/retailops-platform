import { Suspense } from "react";
import { AnalyticsContent } from "./AnalyticsContent";

// docs/PRODUCT-SPEC.md §24 Analytics / BUILD.md Stage 8.
// Wired to real GET /analytics/* endpoints.
export default function AnalyticsPage() {
  return (
    <Suspense fallback={null}>
      <AnalyticsContent />
    </Suspense>
  );
}