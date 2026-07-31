import { EmptyState } from "../../../../components/ui/EmptyState";

// docs/PRODUCT-SPEC.md §24 User Management / BUILD.md Stage 9.
// See docs/stockpilot-gaps.md #4 and #5: StockPilot Core's User model has
// no role field and no user-management API beyond /auth/register today.
export default function UsersSettingsPage() {
  return (
    <EmptyState
      title="Users"
      description="Team member management will appear here once StockPilot Core has a user-management API to build Stage 9 against."
    />
  );
}
