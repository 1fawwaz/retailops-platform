"use client";

import { useSyncExternalStore } from "react";
import { getSession } from "../auth/session";
import { getCachedPermissions, permissionsSnapshot } from "../auth/permissionsCache";
import { subscribeToSessionChanges } from "../auth/useSession";
import type { Permission } from "./permissions";

/**
 * Real permission check (Backend Module 10, docs/ARCHITECTURE.md §7):
 * reads the permission set GET /me resolved and lib/auth/session.ts /
 * lib/auth/refreshPermissions.ts cached, not a hardcoded role. This
 * used to hardcode "admin" for every session (docs/stockpilot-gaps.md
 * #5) because StockPilot Core had no role field at all -- it does now,
 * and this reads the real thing. Still a UI-level convenience only
 * (CLAUDE.md §12): StockPilot Core re-checks every mutating call
 * itself regardless of what this returns.
 *
 * Non-reactive: reads localStorage directly, so a caller outside
 * React's render cycle (or that can't rely on an ancestor re-rendering
 * it after the async /me fetch resolves) may see stale data until
 * something else triggers a re-render. components/layout/LeftNav.tsx
 * uses this specifically because a hook can't be called inside
 * .map(); useCan() below is the reactive equivalent for everywhere
 * else.
 */
export function can(permission: Permission): boolean {
  const session = getSession();
  if (!session) return false;
  return getCachedPermissions().includes(permission);
}

function getServerSnapshot(): string {
  return "";
}

/** Client Component hook -- reactive: re-renders when the permissions
 * cache changes (e.g. once login's or RouteGuard's /me fetch
 * resolves), not just when an ancestor happens to re-render for an
 * unrelated reason. */
export function useCan(permission: Permission): boolean {
  useSyncExternalStore(subscribeToSessionChanges, permissionsSnapshot, getServerSnapshot);
  return can(permission);
}

export type { Permission, Role } from "./permissions";
