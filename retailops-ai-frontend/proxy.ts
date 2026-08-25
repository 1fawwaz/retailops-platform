import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE_NAME } from "@/lib/session";

/**
 * Cheap, presence-only gate: redirects to /login if the session cookie
 * is missing. Does NOT verify the JWT itself (Proxy runs on the Edge
 * runtime, no server-only JWT-decoding dependency here) -- actual
 * verification happens per request on retailops-ai (api/deps.py), and
 * app/api/agent/query/route.ts clears the cookie the moment retailops-ai
 * rejects a stale one. This is UX routing, not the authorization
 * boundary -- Next.js's own docs for this file explicitly warn Proxy
 * "should not be used as a full session management or authorization
 * solution."
 */
export function proxy(request: NextRequest): NextResponse {
  const isAuthenticated = request.cookies.has(SESSION_COOKIE_NAME);
  const { pathname } = request.nextUrl;

  if (pathname.startsWith("/login")) {
    if (isAuthenticated) {
      return NextResponse.redirect(new URL("/chat", request.url));
    }
    return NextResponse.next();
  }

  if (!isAuthenticated) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/", "/chat/:path*", "/login"],
};
