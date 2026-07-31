import { login as loginRequest } from "../api/auth";
import { clearToken, decodeToken, getToken, isTokenExpired, setToken } from "./token";
import { notifySessionChanged } from "./useSession";

export interface Session {
  email: string;
  expiresAt: Date;
}

export async function login(email: string, password: string): Promise<Session> {
  const token = await loginRequest(email, password);
  setToken(token.access_token);
  notifySessionChanged();
  const session = getSession();
  if (!session) {
    // The token we just received doesn't decode into a usable session --
    // a real bug (a malformed token from the server, or expired the
    // instant it arrived), not a normal error path for a caller to
    // handle field-by-field.
    throw new Error("Received an invalid session token from the server.");
  }
  return session;
}

/**
 * No server-side logout endpoint exists (docs/adr/001-session-management.md,
 * docs/stockpilot-gaps.md) -- this only clears local state. The token
 * remains technically valid server-side until its own expiry.
 */
export function logout(): void {
  clearToken();
  notifySessionChanged();
}

export function getSession(): Session | null {
  const token = getToken();
  if (!token || isTokenExpired(token)) return null;
  const claims = decodeToken(token);
  if (!claims) return null;
  return { email: claims.sub, expiresAt: new Date(claims.exp * 1000) };
}
