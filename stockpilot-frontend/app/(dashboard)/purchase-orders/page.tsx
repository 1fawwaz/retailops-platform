import { EmptyState } from "../../../components/ui/EmptyState";

// docs/PRODUCT-SPEC.md §24 Purchase Orders / BUILD.md Stage 5.
// See docs/stockpilot-gaps.md #4: StockPilot Core has no Purchase Order
// API today -- this page can only ever be an empty shell until that's
// resolved, not just "not yet built."
export default function PurchaseOrdersPage() {
  return (
    <EmptyState
      title="Purchase Orders"
      description="Purchase order tracking will appear here once StockPilot Core has a Purchase Orders API to build Stage 5 against."
    />
  );
}
