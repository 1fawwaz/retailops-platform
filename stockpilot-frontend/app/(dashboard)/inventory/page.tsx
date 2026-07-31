import { Suspense } from "react";
import { InventoryContent } from "./InventoryContent";

// docs/PRODUCT-SPEC.md §24 Inventory / BUILD.md Stage 2. Wired to real
// GET /inventory/stock (search, category, low_stock, server-side
// pagination) -- see InventoryContent.tsx. Warehouse/location filter,
// supplier filter, and bulk actions are not built: no backend support
// (docs/stockpilot-gaps.md), stated on the page rather than omitted
// silently. useSearchParams (for URL-reflected filter state per
// docs/PRODUCT-SPEC.md §19) requires this Suspense boundary.
export default function InventoryPage() {
  return (
    <Suspense fallback={null}>
      <InventoryContent />
    </Suspense>
  );
}
