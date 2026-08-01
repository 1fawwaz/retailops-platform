import { getMe } from "../api/auth";
import { hasCachedPermissions, setCachedPermissions } from "./permissionsCache";
import { notifySessionChanged } from "./useSession";

let inFlight: Promise<void> | null = null;

/**
 * Called once on app boot (RouteGuard) to populate the permissions
 * cache when a session already exists but the cache doesn't yet (a
 * page refresh, or a tab opened with an existing token) -- login()
 * itself already populates the cache directly, so this is the other
 * half of the same real-permissions story, not a duplicate of it.
 */
export function ensurePermissionsLoaded(): void {
  if (hasCachedPermissions()) return;
  if (inFlight) return;
  inFlight = getMe()
    .then((me) => {
      setCachedPermissions(me.roles, me.permissions);
      notifySessionChanged();
    })
    .catch(() => {
      // A failed fetch here shouldn't crash the shell -- can()/useCan()
      // simply deny (empty permission set) until a later call succeeds.
    })
    .finally(() => {
      inFlight = null;
    });
}
