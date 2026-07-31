import { EmptyState } from "../../../../components/ui/EmptyState";

// docs/PRODUCT-SPEC.md §24 Role Management / BUILD.md Stage 9.
// See docs/stockpilot-gaps.md #5: no role/permission model exists on the
// backend to manage yet.
export default function RolesSettingsPage() {
  return (
    <EmptyState
      title="Roles"
      description="Role and permission management will appear here once StockPilot Core has a role model to build Stage 9 against."
    />
  );
}
