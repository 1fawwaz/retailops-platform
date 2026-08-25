import { AppError, networkAppError, toAppError } from "./errors";
import { clearCachedPermissions } from "../auth/permissionsCache";
import {
  clearToken,
  getRefreshToken,
  getToken,
  isTokenExpired,
  setAccessToken,
  setRefreshToken,
} from "../auth/token";
import { notifySessionChanged } from "../auth/useSession";
import { accessTokenResponseSchema } from "../validation/auth";

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
  /** Skip attaching the Authorization header -- only /auth/{login,register,refresh,logout}. */
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

function clearSession(): void {
  clearToken();
  clearCachedPermissions();
  notifySessionChanged();
}

/**
 * A raw fetch, not a call through apiFetch: lib/api/auth.ts's
 * refreshAccessToken() wraps apiFetch, and apiFetch needs to call a
 * refresh from inside itself (below) -- going through that wrapper
 * would be a real import cycle (lib/api/auth.ts already imports
 * apiFetch from this file). Returns the new access token, or null if
 * there's no refresh token or the refresh itself failed.
 */
async function silentRefresh(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  try {
    const response = await fetch(buildUrl("/auth/refresh"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(refreshToken ? { refresh_token: refreshToken } : {}),
    });
    if (!response.ok) return null;
    const parsed = accessTokenResponseSchema.parse(await response.json());
    // SEC-02: /auth/refresh rotates the refresh token -- persist the new
    // one or the next silent refresh would present an already-used token.
    if (parsed.refresh_token) setRefreshToken(parsed.refresh_token);
    if (parsed.access_token) setAccessToken(parsed.access_token);
    return parsed.access_token;
  } catch {
    return null;
  }
}

/**
 * docs/ARCHITECTURE.md § Authentication flow: on a 401, or when the
 * stored access token has already expired client-side, this attempts
 * one silent refresh before falling back to clearing the session and
 * letting the caller's route guard redirect to /login. No second
 * retry -- a refreshed-but-still-401 response is a real auth failure,
 * not a transient one.
 */
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return doFetch<T>(path, options, false);
}

async function doFetch<T>(path: string, options: RequestOptions, isRetry: boolean): Promise<T> {
  const { method = "GET", params, body, form, skipAuth = false } = options;

  let token = skipAuth ? null : getToken();
  if (!skipAuth && token && isTokenExpired(token) && !isRetry) {
    token = await silentRefresh();
    if (!token) {
      clearSession();
      throw new AppError("auth", "Your session has expired. Please log in again.", {
        status: 401,
      });
    }
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
    response = await fetch(buildUrl(path, params), {
      method,
      headers,
      body: requestBody,
      credentials: "include",
    });
  } catch (cause) {
    throw networkAppError(cause);
  }

  if (!response.ok) {
    if (response.status === 401 && !skipAuth && !isRetry) {
      const refreshed = await silentRefresh();
      if (refreshed) return doFetch<T>(path, options, true);
    }
    const appError = await toAppError(response);
    if (appError.kind === "auth") clearSession();
    throw appError;
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
