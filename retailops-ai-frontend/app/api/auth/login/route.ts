import { NextResponse } from "next/server";
import { setSessionCookie } from "@/lib/session";

/**
 * Proxies to StockPilot Core's own POST /auth/login (OAuth2
 * password-flow, form-encoded `username`/`password`) -- see
 * retailops-ai/api/deps.py's own docstring for why retailops-ai has no
 * login endpoint of its own and validates StockPilot-issued tokens
 * only. Runs server-side so the STOCKPILOT_BASE_URL env var and the
 * resulting JWT never reach the browser directly.
 */
export async function POST(request: Request): Promise<Response> {
  let body: { email?: unknown; password?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Malformed request body." }, { status: 400 });
  }

  if (typeof body.email !== "string" || typeof body.password !== "string") {
    return NextResponse.json({ detail: "Email and password are required." }, { status: 400 });
  }

  const stockpilotBaseUrl = process.env.STOCKPILOT_BASE_URL;
  if (!stockpilotBaseUrl) {
    return NextResponse.json(
      { detail: "Server misconfigured: STOCKPILOT_BASE_URL is not set." },
      { status: 500 },
    );
  }

  const form = new URLSearchParams();
  form.set("username", body.email);
  form.set("password", body.password);

  let upstream: Response;
  try {
    upstream = await fetch(`${stockpilotBaseUrl}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form.toString(),
    });
  } catch {
    return NextResponse.json(
      { detail: "Could not reach StockPilot. Is it running?" },
      { status: 502 },
    );
  }

  if (!upstream.ok) {
    const detail =
      upstream.status === 401 ? "Incorrect email or password." : "Login failed.";
    return NextResponse.json({ detail }, { status: upstream.status });
  }

  const { access_token: accessToken } = (await upstream.json()) as { access_token: string };
  await setSessionCookie(accessToken);
  return NextResponse.json({ ok: true });
}
