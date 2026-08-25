/**
 * The frontend never runs its own login -- CLAUDE.md: "no second user
 * system." A StockPilot-issued JWT (POST /auth/login) is stored in an
 * httpOnly cookie set by app/api/auth/login/route.ts, so it's never
 * readable by client-side JS (XSS-safer than localStorage). Every other
 * request that needs it goes through a Route Handler proxy
 * (app/api/agent/query/route.ts) which reads the cookie server-side and
 * attaches it as `Authorization: Bearer <token>` -- the same scheme
 * retailops-ai's own api/deps.py::get_current_subject expects.
 */
import { cookies } from "next/headers";

export const SESSION_COOKIE_NAME = "retailops_session";

/** Decodes a JWT's payload without verifying the signature -- safe here
 * because the token is read back only immediately after receiving it
 * fresh from StockPilot's own /auth/login, purely to size the cookie's
 * own lifetime to the token's real `exp` claim rather than a guessed or
 * hardcoded duration. Every real authorization check still happens
 * server-side, per request, on retailops-ai (which DOES verify the
 * signature).
 */
function decodeJwtExpiry(token: string): Date | null {
  const parts = token.split(".");
  if (parts.length !== 3) {
    return null;
  }
  try {
    const payloadJson = Buffer.from(parts[1], "base64url").toString("utf-8");
    const payload = JSON.parse(payloadJson) as { exp?: number };
    if (typeof payload.exp !== "number") {
      return null;
    }
    return new Date(payload.exp * 1000);
  } catch {
    return null;
  }
}

export async function setSessionCookie(token: string): Promise<void> {
  const cookieStore = await cookies();
  const expires = decodeJwtExpiry(token) ?? undefined;
  cookieStore.set(SESSION_COOKIE_NAME, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    expires,
  });
}

export async function getSessionToken(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get(SESSION_COOKIE_NAME)?.value ?? null;
}

export async function clearSessionCookie(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(SESSION_COOKIE_NAME);
}
