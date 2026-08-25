import { Suspense } from "react";
import { SalesOrdersContent } from "./SalesOrdersContent";

// docs/PRODUCT-SPEC.md §24 Sales / BUILD.md Stage 7.
// Wired to real GET /sales-orders (status filter, server-side pagination).
export default function SalesOrdersPage() {
  return (
    <Suspense fallback={null}>
      <SalesOrdersContent />
    </Suspense>
  );
}