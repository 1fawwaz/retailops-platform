"use client";

import { useSyncExternalStore } from "react";
import { permissionsSnapshot } from "./permissionsCache";
import { decodeToken, getToken, isTokenExpired } from "./token";
import type { Session } from "./session";

// react-hooks' set-state-in-effect rule (correctly) rejects
// useEffect+useState for reading external mutable state like
// localStorage -- useSyncExternalStore is the built-in, hydration-safe
// primitive for exactly this, and self-corrects the SSR-vs-client
// snapshot mismatch (server always sees "no token") without a manual
// effect. lib/auth/session.ts's login()/logout() call
// notifySessionChanged() so this store's subscribers re-render.
const SESSION_EVENT = "stockpilot:session-changed";

export function notifySessionChanged(): void {
  window.dispatchEvent(new Event(SESSION_EVENT));
}

/** Exported so lib/rbac/index.ts's useCan() can subscribe to the same
 * event/storage pair without duplicating this wiring. */
export function subscribeToSessionChanges(callback: () => void): () => void {
  window.addEventListener(SESSION_EVENT, callback);
  window.addEventListener("storage", callback);
  return () => {
    window.removeEventListener(SESSION_EVENT, callback);
    window.removeEventListener("storage", callback);
  };
}

// Composite of the raw token AND the cached-permissions blob: a
// primitive string, trivially stable for useSyncExternalStore's
// equality check, but one that changes when EITHER changes -- a
// permissions-only update (no token change, e.g. after login's /me
// fetch resolves) must still trigger a re-render for components
// reading useCan(). Deriving the Session object happens in
// useSession() below, not here.
function getSnapshot(): string {
  return `${getToken() ?? ""}::${permissionsSnapshot()}`;
}

function getServerSnapshot(): string {
  return "";
}

export function useSession(): Session | null {
  // The snapshot's only job is to change (any change) when it's time to
  // re-render; the actual session is always derived fresh from the real
  // token, not parsed back out of the composite string above.
  useSyncExternalStore(subscribeToSessionChanges, getSnapshot, getServerSnapshot);
  const token = getToken();
  if (!token || isTokenExpired(token)) return null;
  const claims = decodeToken(token);
  if (!claims) return null;
  return { email: claims.sub, expiresAt: new Date(claims.exp * 1000) };
}
