import type { Permission } from "../../lib/rbac";

export interface NavItem {
  label: string;
  href: string;
  /** Gates visibility per lib/rbac -- undefined means every authenticated role sees it. */
  permission?: Permission;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

// One entry per docs/PRODUCT-SPEC.md §24 page. Drives the left nav render
// AND the Stage 0 acceptance criterion "every nav item routes to a real
// (empty-state) page -- no 404s in the primary nav": each href below has
// a matching app/(dashboard)/... page.tsx.
export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Overview",
    items: [{ label: "Dashboard", href: "/dashboard", permission: "dashboard:read" }],
  },
  {
    label: "Operations",
    items: [
      { label: "Products", href: "/products", permission: "products:read" },
      { label: "Inventory", href: "/inventory", permission: "inventory:read" },
      { label: "Suppliers", href: "/suppliers", permission: "suppliers:read" },
      { label: "Purchase Orders", href: "/purchase-orders", permission: "purchase_order:read" },
    ],
  },
  {
    label: "Sales",
    items: [
      { label: "Orders", href: "/sales/orders", permission: "sales:read" },
      { label: "Customers", href: "/sales/customers", permission: "customers:read" },
    ],
  },
  {
    label: "Insight",
    items: [
      { label: "Forecasts", href: "/forecasts", permission: "forecasts:read" },
      { label: "Analytics", href: "/analytics", permission: "analytics:read" },
      { label: "Reports", href: "/reports", permission: "reports:read" },
    ],
  },
  {
    label: "Admin",
    items: [
      { label: "Notifications", href: "/notifications", permission: "notifications:read" },
      { label: "Audit Logs", href: "/audit-logs", permission: "audit_logs:read" },
      { label: "Users", href: "/settings/users", permission: "users:read" },
      { label: "Roles", href: "/settings/roles", permission: "roles:read" },
      { label: "API Keys", href: "/settings/api-keys", permission: "settings:read" },
    ],
  },
];
