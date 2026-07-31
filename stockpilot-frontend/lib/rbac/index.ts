import { getSession } from "../auth/session";
import { roleCan, type Permission, type Role } from "./permissions";

/**
 * docs/stockpilot-gaps.md #5: StockPilot Core's User model has no role
 * field, so there is no real source to read a role from yet. Every
 * authenticated session is placeholder-assigned the most-permissive
 * role so the app is usable end-to-end during Stage 0-8 development,
 * NOT because every real user should be an admin -- replace this
 * function's body, and only this function's body, the moment a real
 * role claim/endpoint exists server-side. CLAUDE.md §12: this is a
 * UI-level convenience, never the actual security boundary.
 */
function currentRole(): Role | null {
  const session = getSession();
  if (!session) return null;
  return "admin";
}

/** Server Component / route-guard equivalent of useCan below. */
export function can(permission: Permission): boolean {
  const role = currentRole();
  if (!role) return false;
  return roleCan(role, permission);
}

/** Client Component hook -- same check, React-friendly call shape. */
export function useCan(permission: Permission): boolean {
  return can(permission);
}

export type { Permission, Role } from "./permissions";
