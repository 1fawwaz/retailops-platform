import { Suspense } from "react";
import { ReportsContent } from "./ReportsContent";

// docs/PRODUCT-SPEC.md §24 Reports / §15 / BUILD.md Stage 8.
// Wired to real GET /analytics/* endpoints.
export default function ReportsPage() {
  return (
    <Suspense fallback={null}>
      <ReportsContent />
    </Suspense>
  );
}