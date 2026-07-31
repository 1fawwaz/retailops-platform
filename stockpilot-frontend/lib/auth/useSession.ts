"use client";

import { useSyncExternalStore } from "react";
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

function subscribe(callback: () => void): () => void {
  window.addEventListener(SESSION_EVENT, callback);
  window.addEventListener("storage", callback);
  return () => {
    window.removeEventListener(SESSION_EVENT, callback);
    window.removeEventListener("storage", callback);
  };
}

// Returns the raw token string (or null) -- a primitive, so it's
// trivially stable for useSyncExternalStore's equality check. Deriving
// the Session object happens in useSession() below, not here.
function getSnapshot(): string | null {
  return getToken();
}

function getServerSnapshot(): string | null {
  return null;
}

export function useSession(): Session | null {
  const token = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  if (!token || isTokenExpired(token)) return null;
  const claims = decodeToken(token);
  if (!claims) return null;
  return { email: claims.sub, expiresAt: new Date(claims.exp * 1000) };
}
