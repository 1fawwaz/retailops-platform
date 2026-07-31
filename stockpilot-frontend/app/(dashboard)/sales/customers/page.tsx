import { EmptyState } from "../../../../components/ui/EmptyState";

// docs/PRODUCT-SPEC.md §24 Customers / BUILD.md Stage 6.
// See docs/stockpilot-gaps.md #4: StockPilot Core has no Customers API today.
export default function CustomersPage() {
  return (
    <EmptyState
      title="Customers"
      description="Customer records will appear here once StockPilot Core has a Customers API to build Stage 6 against."
    />
  );
}
