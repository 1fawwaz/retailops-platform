import { Suspense } from "react";
import { ProductsContent } from "./ProductsContent";

// docs/PRODUCT-SPEC.md §24 Products / BUILD.md "Frontend -- Products".
// Wired to real GET /products (search, category, server-side pagination,
// commit 1179357). useSearchParams (URL-reflected filter state per
// docs/PRODUCT-SPEC.md §19) requires this Suspense boundary.
export default function ProductsPage() {
  return (
    <Suspense fallback={null}>
      <ProductsContent />
    </Suspense>
  );
}
