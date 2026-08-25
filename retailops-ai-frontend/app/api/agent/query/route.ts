import { NextResponse } from "next/server";
import { clearSessionCookie, getSessionToken } from "@/lib/session";

/**
 * Proxies to retailops-ai's own POST /agent/query, forwarding whichever
 * Accept header the client sent -- that same endpoint serves either a
 * blocking JSON response (Accept: application/json, F1's original
 * path) or a live SSE stream (Accept: text/event-stream, F2) from the
 * SAME upstream call, so this proxy just needs to relay the header and
 * then relay whichever kind of body comes back, rather than branching
 * into two different upstream requests.
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

  const acceptHeader = request.headers.get("accept") ?? "application/json";

  let upstream: Response;
  try {
    upstream = await fetch(`${retailopsBaseUrl}/agent/query`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: acceptHeader,
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
    // A 401 is always a plain JSON body (the auth dependency rejects
    // the request before api/agent.py ever branches into the SSE
    // generator), so this check is safe to run before the
    // streaming-vs-JSON branch below.
    await clearSessionCookie();
  }

  const contentType = upstream.headers.get("content-type") ?? "";
  if (contentType.includes("text/event-stream")) {
    // Pipe the upstream ReadableStream straight through -- no need to
    // parse/re-encode SSE frames here, this proxy only needs to attach
    // auth and relay bytes. upstream.body is null only for a response
    // with no body at all, which api/agent.py's SSE path never sends.
    return new NextResponse(upstream.body, {
      status: upstream.status,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  }

  const responseBody = await upstream.text();
  return new NextResponse(responseBody, {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}
