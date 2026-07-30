import { NextResponse } from "next/server";
import { getSessionToken } from "@/lib/session";

/**
 * Proxies to retailops-ai's own GET /agent/execution/{id} -- the
 * "deeper, fully persisted trace" (api/agent.py's own docstring),
 * including each tool call's raw_response. A citation chip's
 * provenance drawer (Task F4) fetches this once per execution_id and
 * looks up the specific tool_call_id its own citation resolved to,
 * rather than the (lighter, no raw_response) /agent/query response
 * carrying every tool's full raw payload on every turn.
 */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ executionId: string }> },
): Promise<Response> {
  const token = await getSessionToken();
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated." }, { status: 401 });
  }

  const { executionId } = await params;

  const retailopsBaseUrl = process.env.RETAILOPS_BASE_URL;
  if (!retailopsBaseUrl) {
    return NextResponse.json(
      { detail: "Server misconfigured: RETAILOPS_BASE_URL is not set." },
      { status: 500 },
    );
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${retailopsBaseUrl}/agent/execution/${executionId}`, {
      headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
    });
  } catch {
    return NextResponse.json(
      { detail: "Could not reach RetailOps AI. Is it running?" },
      { status: 502 },
    );
  }

  const responseBody = await upstream.text();
  return new NextResponse(responseBody, {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}
