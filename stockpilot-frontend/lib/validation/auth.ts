import { z } from "zod";

// Mirrors contracts/stockpilot-api/schemas/login_auth_login_post.json
// exactly -- StockPilot Core's real /auth/login response shape.
// refresh_token is now always present (Backend Module 1); see
// docs/adr/001-session-management.md for why this is a bearer token in
// the body, not a cookie.
export const tokenSchema = z.object({
  access_token: z.string(),
  refresh_token: z.string(),
  token_type: z.string().default("bearer"),
});
export type Token = z.infer<typeof tokenSchema>;

// Mirrors contracts/stockpilot-api/schemas/refresh_auth_refresh_post.json.
export const accessTokenResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.string().default("bearer"),
});
export type AccessTokenResponse = z.infer<typeof accessTokenResponseSchema>;

// Mirrors contracts/stockpilot-api/schemas/register_auth_register_post.json's
// UserRead exactly.
export const userReadSchema = z.object({
  id: z.number().int(),
  email: z.string().email(),
  is_active: z.boolean(),
  is_read_only: z.boolean(),
  created_at: z.string(),
});
export type UserRead = z.infer<typeof userReadSchema>;

// Mirrors contracts/stockpilot-api/schemas/me_me_get.json exactly
// (Backend Module 10): the one shape both a profile page and the RBAC
// layer share (docs/ARCHITECTURE.md §6/§7).
export const meReadSchema = z.object({
  user: userReadSchema,
  roles: z.array(z.string()),
  permissions: z.array(z.string()),
});
export type MeRead = z.infer<typeof meReadSchema>;
