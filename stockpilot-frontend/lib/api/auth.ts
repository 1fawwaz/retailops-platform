import { apiFetch } from "./client";
import {
  accessTokenResponseSchema,
  meReadSchema,
  tokenSchema,
  type AccessTokenResponse,
  type MeRead,
  type Token,
} from "../validation/auth";

/**
 * StockPilot Core's /auth/login expects
 * application/x-www-form-urlencoded (OAuth2 password-grant shape, a
 * FastAPI convention), not JSON -- see contracts/stockpilot-api/versions/v1.json.
 */
export async function login(email: string, password: string): Promise<Token> {
  const raw = await apiFetch<unknown>("/auth/login", {
    method: "POST",
    form: { username: email, password },
    skipAuth: true,
  });
  return tokenSchema.parse(raw);
}

/** Idempotent server-side (docs/ARCHITECTURE.md §6): always 204, even
 * for an already-revoked or unknown refresh token. */
export async function logoutRequest(refreshToken: string): Promise<void> {
  await apiFetch<undefined>("/auth/logout", {
    method: "POST",
    body: { refresh_token: refreshToken },
    skipAuth: true,
  });
}

export async function refreshAccessToken(refreshToken: string): Promise<AccessTokenResponse> {
  const raw = await apiFetch<unknown>("/auth/refresh", {
    method: "POST",
    body: { refresh_token: refreshToken },
    skipAuth: true,
  });
  return accessTokenResponseSchema.parse(raw);
}

export async function getMe(): Promise<MeRead> {
  const raw = await apiFetch<unknown>("/me");
  return meReadSchema.parse(raw);
}
