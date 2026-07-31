import { AppError, networkAppError, toAppError } from "./errors";
import { clearToken, getToken, isTokenExpired } from "../auth/token";
import { notifySessionChanged } from "../auth/useSession";

// docs/ARCHITECTURE.md § API Architecture: the one place a StockPilot
// Core base URL, an Authorization header, and 401 handling exist.
// lib/api/<resource>.ts functions call this, never `fetch` directly.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;

if (!API_BASE_URL && typeof window !== "undefined") {
  // Loud, not silent -- a missing env var should fail obviously in dev,
  // not manifest as a confusing relative-URL fetch failure later.
  console.error(
    "NEXT_PUBLIC_API_BASE_URL is not set. See docs/ARCHITECTURE.md § Environment Variables.",
  );
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  params?: Record<string, string | number | boolean | undefined>;
  body?: unknown;
  /** application/x-www-form-urlencoded instead of JSON -- only /auth/login needs this. */
  form?: Record<string, string>;
  /** Skip attaching the Authorization header -- only /auth/login and /auth/register. */
  skipAuth?: boolean;
}

function buildUrl(path: string, params?: RequestOptions["params"]): string {
  const url = new URL(path, API_BASE_URL ?? "http://localhost");
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

/**
 * On a 401: this frontend has no refresh mechanism (StockPilot Core
 * issues no refresh token -- see docs/adr/001-session-management.md and
 * docs/stockpilot-gaps.md), so a 401 clears the stored token and lets
 * the caller's route guard redirect to /login. No retry is attempted.
 */
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", params, body, form, skipAuth = false } = options;

  const token = skipAuth ? null : getToken();
  if (!skipAuth && token && isTokenExpired(token)) {
    clearToken();
    notifySessionChanged();
    throw new AppError("auth", "Your session has expired. Please log in again.", { status: 401 });
  }

  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  let requestBody: BodyInit | undefined;
  if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    requestBody = new URLSearchParams(form).toString();
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    requestBody = JSON.stringify(body);
  }

  let response: Response;
  try {
    response = await fetch(buildUrl(path, params), { method, headers, body: requestBody });
  } catch (cause) {
    throw networkAppError(cause);
  }

  if (!response.ok) {
    const appError = await toAppError(response);
    if (appError.kind === "auth") {
      clearToken();
      notifySessionChanged();
    }
    throw appError;
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
