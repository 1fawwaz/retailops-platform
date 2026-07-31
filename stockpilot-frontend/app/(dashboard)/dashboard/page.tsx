import { DashboardContent } from "./DashboardContent";

// docs/PRODUCT-SPEC.md §24 Dashboard / BUILD.md Stage 1. KPI cards and
// the revenue chart are wired to real StockPilot Core endpoints
// (/analytics/revenue, /inventory/valuation, /inventory/low-stock) --
// see DashboardContent.tsx. Open PO count and the activity feed are not
// built: no backend endpoint exists for either (docs/stockpilot-gaps.md
// #4), and this page states that plainly rather than approximating it.
export default function DashboardPage() {
  return <DashboardContent />;
}
