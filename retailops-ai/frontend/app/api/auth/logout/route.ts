import { NextResponse } from "next/server";
import { clearSessionCookie } from "@/lib/session";

export async function POST(): Promise<Response> {
  await clearSessionCookie();
  return NextResponse.json({ ok: true });
}
