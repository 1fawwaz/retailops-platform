// docs/adr/001-session-management.md: StockPilot Core issues a bearer
// token in the response body, not a cookie -- this module is the one
// place that token is stored/read/cleared. Client-side localStorage,
// origin-scoped (does not survive across stockpilot.<domain> /
// ai.stockpilot.<domain>, by design -- see the ADR).
const STORAGE_KEY = "stockpilot.access_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(STORAGE_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(STORAGE_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(STORAGE_KEY);
}

interface DecodedTokenClaims {
  sub: string;
  exp: number;
}

/**
 * Decodes the JWT payload WITHOUT verifying the signature -- reading a
 * claim to display (e.g. the user's email from `sub`) or checking
 * client-side expiry for UX purposes only. This is never a substitute
 * for server-side verification: StockPilot Core re-validates the
 * signature on every request per CLAUDE.md §12, "the frontend is never
 * the sole enforcement point."
 */
export function decodeToken(token: string): DecodedTokenClaims | null {
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  try {
    const payload = JSON.parse(atob(parts[1].replace(/-/g, "+").replace(/_/g, "/")));
    if (typeof payload.sub !== "string" || typeof payload.exp !== "number") return null;
    return { sub: payload.sub, exp: payload.exp };
  } catch {
    return null;
  }
}

export function isTokenExpired(token: string): boolean {
  const claims = decodeToken(token);
  if (!claims) return true;
  return claims.exp * 1000 <= Date.now();
}
