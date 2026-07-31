import { EmptyState } from "../../../components/ui/EmptyState";

// docs/PRODUCT-SPEC.md §24 Audit Logs / BUILD.md Stage 9.
// See docs/stockpilot-gaps.md #4: StockPilot Core has no Audit Log API today.
export default function AuditLogsPage() {
  return (
    <EmptyState
      title="Audit Logs"
      description="A chronological record of business-record changes will appear here once StockPilot Core has an Audit Log API to build against."
    />
  );
}
