// docs/PRODUCT-SPEC.md §6's six-role model, encoded as real permission
// data. See docs/stockpilot-gaps.md #5: StockPilot Core has no role field
// on its User model today, so nothing yet assigns a real role to a real
// user -- see ./index.ts's useCurrentRole for where that placeholder lives.
// This file is the part that IS real: the shape a role check takes, and
// the intended permission set per role, ready to wire to a real source
// the moment StockPilot Core has one.

export type Role =
  | "admin"
  | "inventory_manager"
  | "procurement"
  | "sales"
  | "analyst"
  | "viewer";

export type Resource =
  | "dashboard"
  | "products"
  | "inventory"
  | "suppliers"
  | "purchase_order"
  | "sales"
  | "customers"
  | "forecasts"
  | "analytics"
  | "reports"
  | "notifications"
  | "audit_logs"
  | "settings"
  | "users"
  | "roles"
  | "profile";

export type Action = "read" | "create" | "update" | "delete" | "receive";

export type Permission = `${Resource}:${Action}`;

const ALL_RESOURCES: Resource[] = [
  "dashboard",
  "products",
  "inventory",
  "suppliers",
  "purchase_order",
  "sales",
  "customers",
  "forecasts",
  "analytics",
  "reports",
  "notifications",
  "audit_logs",
  "settings",
  "users",
  "roles",
  "profile",
];

function readOnly(resources: Resource[]): Permission[] {
  return resources.map((resource): Permission => `${resource}:read`);
}

function fullAccess(resources: Resource[]): Permission[] {
  const actions: Action[] = ["read", "create", "update", "delete"];
  return resources.flatMap((resource) => actions.map((action): Permission => `${resource}:${action}`));
}

const ALL_ACTIONS: Action[] = ["read", "create", "update", "delete", "receive"];

function everyAction(resources: Resource[]): Permission[] {
  return resources.flatMap((resource) => ALL_ACTIONS.map((action): Permission => `${resource}:${action}`));
}

// docs/PRODUCT-SPEC.md §6's table, one entry per row. Admin uses
// everyAction (not fullAccess) deliberately -- "Everything, including
// Settings/Users/Roles" per §6 must include every action any other role
// has, including purchase_order's non-CRUD `receive` action; a caught
// bug (lib/rbac/permissions.test.ts) when this used fullAccess instead.
export const ROLE_PERMISSIONS: Record<Role, ReadonlySet<Permission>> = {
  admin: new Set(everyAction(ALL_RESOURCES)),
  inventory_manager: new Set([
    ...fullAccess(["inventory", "products", "suppliers"]),
    "purchase_order:read",
    "purchase_order:create",
    "purchase_order:receive",
    ...readOnly(["analytics", "dashboard", "profile"]),
  ]),
  procurement: new Set([
    ...fullAccess(["suppliers", "purchase_order"]),
    ...readOnly(["inventory", "forecasts", "dashboard", "profile"]),
  ]),
  sales: new Set([
    ...fullAccess(["sales", "customers"]),
    ...readOnly(["products", "inventory", "dashboard", "profile"]),
  ]),
  analyst: new Set(readOnly(["dashboard", "analytics", "reports", "forecasts", "profile"])),
  viewer: new Set(readOnly(["dashboard", "profile"])),
};

export function roleCan(role: Role, permission: Permission): boolean {
  return ROLE_PERMISSIONS[role].has(permission);
}
