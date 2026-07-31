import { EmptyState } from "../../../../components/ui/EmptyState";

// docs/PRODUCT-SPEC.md §24 Sales / BUILD.md Stage 6.
// See docs/stockpilot-gaps.md #4: StockPilot Core has no Sales/Orders API today.
export default function SalesOrdersPage() {
  return (
    <EmptyState
      title="Orders"
      description="Sales orders will appear here once StockPilot Core has a Sales API to build Stage 6 against."
    />
  );
}
