// lib/rbac/index.ts's can()/useCan() are called synchronously (some
// call sites are inside .map(), where hooks/async calls aren't legal --
// see components/layout/LeftNav.tsx's own comment on this). GET /me
// (Backend Module 10) is async, so its result is cached here right
// after it resolves (login, or once on app boot if a token already
// exists) and read back synchronously everywhere a permission check
// happens. Not a security boundary (CLAUDE.md §12) -- StockPilot Core
// re-checks every mutating call itself regardless of what this cache
// says.
const ROLES_KEY = "stockpilot.roles";
const PERMISSIONS_KEY = "stockpilot.permissions";

function readStringArray(key: string): string[] {
  if (typeof window === "undefined") return [];
  const raw = window.localStorage.getItem(key);
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.every((item) => typeof item === "string")
      ? parsed
      : [];
  } catch {
    return [];
  }
}

export function getCachedRoles(): string[] {
  return readStringArray(ROLES_KEY);
}

export function getCachedPermissions(): string[] {
  return readStringArray(PERMISSIONS_KEY);
}

/** A user can genuinely have zero permissions (no roles assigned yet,
 * Backend Module 10) -- an empty cached array is a valid loaded state,
 * not "hasn't been fetched." This checks for that distinction directly
 * rather than inferring it from array length. */
export function hasCachedPermissions(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(PERMISSIONS_KEY) !== null;
}

export function setCachedPermissions(roles: string[], permissions: string[]): void {
  window.localStorage.setItem(ROLES_KEY, JSON.stringify(roles));
  window.localStorage.setItem(PERMISSIONS_KEY, JSON.stringify(permissions));
}

export function clearCachedPermissions(): void {
  window.localStorage.removeItem(ROLES_KEY);
  window.localStorage.removeItem(PERMISSIONS_KEY);
}

/** Composite snapshot string for useSyncExternalStore -- changes
 * whenever either cached array changes, so a permissions-only update
 * (no token change) still triggers a re-render. */
export function permissionsSnapshot(): string {
  if (typeof window === "undefined") return "";
  return (
    (window.localStorage.getItem(ROLES_KEY) ?? "") +
    "::" +
    (window.localStorage.getItem(PERMISSIONS_KEY) ?? "")
  );
}
