import { Suspense } from "react";
import { CustomersContent } from "./CustomersContent";

// docs/PRODUCT-SPEC.md §24 Customers / BUILD.md Stage 6.
// Wired to real GET /customers (search, server-side pagination).
export default function CustomersPage() {
  return (
    <Suspense fallback={null}>
      <CustomersContent />
    </Suspense>
  );
}