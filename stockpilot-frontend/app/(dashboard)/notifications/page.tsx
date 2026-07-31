import { EmptyState } from "../../../components/ui/EmptyState";

// docs/PRODUCT-SPEC.md §24 Notifications / §16 / BUILD.md Stage 9.
// See docs/stockpilot-gaps.md #4: StockPilot Core has no Notifications API today.
export default function NotificationsPage() {
  return (
    <EmptyState
      title="Notifications"
      description="System-generated alerts will appear here once StockPilot Core has a Notifications API to build against."
    />
  );
}
