import { getMe, login as loginRequest, logoutRequest } from "../api/auth";
import { clearCachedPermissions, setCachedPermissions } from "./permissionsCache";
import {
  clearToken,
  decodeToken,
  getRefreshToken,
  getToken,
  isTokenExpired,
  setToken,
} from "./token";
import { notifySessionChanged } from "./useSession";

export interface Session {
  email: string;
  expiresAt: Date;
}

export async function login(email: string, password: string): Promise<Session> {
  const token = await loginRequest(email, password);
  setToken(token.access_token, token.refresh_token);
  notifySessionChanged();
  const session = getSession();
  if (!session) {
    // The token we just received doesn't decode into a usable session --
    // a real bug (a malformed token from the server, or expired the
    // instant it arrived), not a normal error path for a caller to
    // handle field-by-field.
    throw new Error("Received an invalid session token from the server.");
  }
  // Fetch and cache the real permission set (Backend Module 10) so
  // lib/rbac's synchronous can()/useCan() have real data as soon as
  // the dashboard renders, not just after its own first check.
  try {
    const me = await getMe();
    setCachedPermissions(me.roles, me.permissions);
    notifySessionChanged();
  } catch {
    // A failed /me right after a successful login is a real backend
    // problem, but shouldn't block the login itself from completing --
    // lib/auth/refreshPermissions.ts's boot-time fetch (run by
    // RouteGuard) will retry.
  }
  return session;
}

/**
 * Revokes the refresh token server-side (Backend Module 1,
 * docs/ARCHITECTURE.md §6 -- idempotent, always succeeds from the
 * caller's perspective) then clears local state regardless of whether
 * the network call succeeded, so the user is never stuck "logged in"
 * locally after clicking Log out.
 */
export async function logout(): Promise<void> {
  const refreshToken = getRefreshToken();
  if (refreshToken) {
    try {
      await logoutRequest(refreshToken);
    } catch {
      // Local logout still proceeds -- see docstring above.
    }
  }
  clearToken();
  clearCachedPermissions();
  notifySessionChanged();
}

export function getSession(): Session | null {
  const token = getToken();
  if (!token || isTokenExpired(token)) return null;
  const claims = decodeToken(token);
  if (!claims) return null;
  return { email: claims.sub, expiresAt: new Date(claims.exp * 1000) };
}
