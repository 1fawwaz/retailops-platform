import { EmptyState } from "../../../components/ui/EmptyState";

// docs/PRODUCT-SPEC.md §24 Dashboard / §11 KPIs / BUILD.md Stage 1.
// Real KPI cards, revenue chart, and activity feed land in Stage 1 --
// this is Stage 0's required empty-state shell, not a stub pretending
// to be finished.
export default function DashboardPage() {
  return (
    <EmptyState
      title="Dashboard"
      description="KPI cards, revenue trend, and recent activity will appear here once Stage 1 wires real StockPilot Core data."
    />
  );
}
