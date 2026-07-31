import { apiFetch } from "./client";
import { tokenSchema, type Token } from "../validation/auth";

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
