import { z } from "zod";

// Mirrors contracts/stockpilot-api/schemas/login_auth_login_post.json
// exactly -- StockPilot Core's real /auth/login response shape, not an
// assumed one. See docs/adr/001-session-management.md for why this is a
// bearer token in the body, not a cookie.
export const tokenSchema = z.object({
  access_token: z.string(),
  token_type: z.string().default("bearer"),
});
export type Token = z.infer<typeof tokenSchema>;

// Mirrors contracts/stockpilot-api/schemas/register_auth_register_post.json's
// UserRead exactly. No `role` field -- see docs/stockpilot-gaps.md #5;
// StockPilot Core's User model has none to expose.
export const userReadSchema = z.object({
  id: z.number().int(),
  email: z.string().email(),
  is_active: z.boolean(),
  is_read_only: z.boolean(),
  created_at: z.string(),
});
export type UserRead = z.infer<typeof userReadSchema>;
