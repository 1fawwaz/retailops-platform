# ADR 001: Session storage falls back to client-held bearer tokens; real cross-domain SSO is deferred

## Status

Accepted — BUILD.md Stage 0.

## Context

`docs/ARCHITECTURE.md` § Session Management flags this as a decision that must be confirmed against StockPilot Core's actual auth implementation before `lib/auth/` is written, since a real shared session across `stockpilot.<domain>` and `ai.stockpilot.<domain>` requires StockPilot Core to issue the session as an `httpOnly`, `Secure` cookie scoped to the parent domain (`Domain=.stockpilot.<domain>`) — not a token returned in the response body for the frontend to store itself.

**Checked against the real contract, not assumed.** `contracts/stockpilot-api/schemas/login_auth_login_post.json` (generated from StockPilot Core's live OpenAPI export) defines the `/auth/login` response as:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

A plain bearer JWT in the response body. No `Set-Cookie` header, no cookie-based session mechanism exists in StockPilot Core today.

## Decision

Stage 0 implements the **documented fallback**: the access token is stored client-side (this frontend) and read per-request via an `Authorization: Bearer <token>` header, per the existing pattern already proven in the RetailOps AI frontend (which consumes the same StockPilot Core auth). Each frontend (`stockpilot-frontend`, RetailOps AI) requires its own independent login — there is no shared-session SSO between `stockpilot.<domain>` and `ai.stockpilot.<domain>` in this implementation.

This is a **deliberate, disclosed limitation**, not a silent gap — per `docs/ARCHITECTURE.md` § Session Management's own instruction: "must be a stated, deliberate limitation in both READMEs, not a silent gap discovered by a confused user later." Both frontend READMEs should state it plainly once Stage 12 (production deployment) writes the final README.

## Why not implement the cookie-based session now

Issuing an `httpOnly`, `Secure`, parent-domain-scoped cookie is **StockPilot Core's** responsibility — `docs/ARCHITECTURE.md` § Session Management is explicit that "neither frontend repo can retrofit it unilaterally." Changing StockPilot Core's `/auth/login` response shape is a backend change to a different, already-deployed service, outside this frontend repo's scope, and not something Stage 0 of a frontend build should silently take on. If real cross-domain SSO becomes a priority, it starts with a StockPilot Core change (issue the cookie) and a corresponding ADR in both frontend repos when that lands — not a retrofit here.

## Consequences

- `lib/auth/` stores the bearer token (not a cookie) and attaches it via `Authorization` header in `lib/api/client.ts`.
- A user working across both StockPilot Frontend and RetailOps AI Frontend logs in twice. This is honest, visible behavior — not hidden behind chrome that implies a single session.
- The "one platform" goal in `docs/PRODUCT-SPEC.md` §2/§9 is only partially met (shared visual identity, not a shared login) until a future StockPilot Core change revisits this.
- No code in this repo should attempt to read or set a cross-domain cookie — that capability doesn't exist server-side to support it.
