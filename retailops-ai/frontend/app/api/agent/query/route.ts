import { NextResponse } from "next/server";
import { clearSessionCookie, getSessionToken } from "@/lib/session";

/**
 * Proxies to retailops-ai's own POST /agent/query -- the plain
 * blocking JSON path specifically (Accept: application/json), not the
 * SSE path (Accept: text/event-stream) that same endpoint also serves.
 * Consuming SSE is F2's own job (BUILD-SPEC.md Stage 6 frontend
 * priority list); F1's chat page only needs a request/response turn.
 *
 * Runs server-side so the httpOnly session cookie (never readable by
 * client JS) can be read here and attached as the Authorization
 * header retailops-ai's api/deps.py::get_current_subject expects.
 */
export async function POST(request: Request): Promise<Response> {
  const token = await getSessionToken();
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated." }, { status: 401 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Malformed request body." }, { status: 400 });
  }

  const retailopsBaseUrl = process.env.RETAILOPS_BASE_URL;
  if (!retailopsBaseUrl) {
    return NextResponse.json(
      { detail: "Server misconfigured: RETAILOPS_BASE_URL is not set." },
      { status: 500 },
    );
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${retailopsBaseUrl}/agent/query`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
    });
  } catch {
    return NextResponse.json(
      { detail: "Could not reach RetailOps AI. Is it running?" },
      { status: 502 },
    );
  }

  if (upstream.status === 401) {
    // The token retailops-ai holds is the same one we just sent, so an
    // upstream 401 means it expired or StockPilot's own JWT_SECRET no
    // longer matches -- either way, this session is dead; clear it so
    // the next request bounces to /login instead of retrying forever.
    await clearSessionCookie();
  }

  const responseBody = await upstream.text();
  return new NextResponse(responseBody, {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}
