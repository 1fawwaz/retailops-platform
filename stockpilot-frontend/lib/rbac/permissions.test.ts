import { describe, expect, it } from "vitest";
import { roleCan } from "./permissions";

// docs/PRODUCT-SPEC.md §6's table, spot-checked per role -- not
// exhaustive over every permission, but enough to catch a role being
// wired to the wrong permission set entirely.
describe("roleCan", () => {
  it("admin can do everything checked, including settings", () => {
    expect(roleCan("admin", "users:delete")).toBe(true);
    expect(roleCan("admin", "purchase_order:receive")).toBe(true);
  });

  it("inventory_manager can receive purchase orders but not manage users", () => {
    expect(roleCan("inventory_manager", "purchase_order:receive")).toBe(true);
    expect(roleCan("inventory_manager", "inventory:update")).toBe(true);
    expect(roleCan("inventory_manager", "users:read")).toBe(false);
  });

  it("procurement has full purchase_order access but only read access to inventory", () => {
    expect(roleCan("procurement", "purchase_order:create")).toBe(true);
    expect(roleCan("procurement", "inventory:read")).toBe(true);
    expect(roleCan("procurement", "inventory:update")).toBe(false);
  });

  it("analyst has no mutation permissions anywhere", () => {
    expect(roleCan("analyst", "analytics:read")).toBe(true);
    expect(roleCan("analyst", "products:create")).toBe(false);
    expect(roleCan("analyst", "inventory:update")).toBe(false);
  });

  it("viewer can only read the dashboard and their own profile", () => {
    expect(roleCan("viewer", "dashboard:read")).toBe(true);
    expect(roleCan("viewer", "profile:read")).toBe(true);
    expect(roleCan("viewer", "inventory:read")).toBe(false);
  });
});
