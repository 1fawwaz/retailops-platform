\# docs/ARCHITECTURE.md — StockPilot Frontend (ERP)



\# 



\*\*What this document is:\*\* the long-term technical reference for this repo and how it fits the wider system — \_how\_ everything is designed and wired. `docs/PRODUCT-SPEC.md` defines \_what\_ the application does; this document never restates product behavior, only how it's technically achieved. `CLAUDE.md` is the engineering-rules doc for how code is written day to day; `BUILD.md` is build order. Keep this file updated when a real architectural decision changes — this is not the place for task-level notes, those live in `BUILD.md` and `docs/adr/`.



\* \* \*



\## 1\\. System architecture — overview



\# 



Four deployables:



|  | StockPilot Core | RetailOps AI Backend | \*\*StockPilot Frontend (this repo)\*\* | RetailOps AI Frontend |

| --- | --- | --- | --- | --- |

| Kind | FastAPI | LangGraph agent service | Next.js | Next.js |

| Owns | PostgreSQL, business APIs, auth | Multi-agent orchestration | Business UI | AI Copilot UI |

| Talks to | — | StockPilot Core APIs only | StockPilot Core APIs, RetailOps AI Backend | RetailOps AI Backend only |

| Deploy | Railway/Fly | Railway/Fly | Vercel (Project A) | Vercel (Project B) |



\*\*Ownership rules:\*\*



\-   Only StockPilot Core touches PostgreSQL and only StockPilot Core issues JWTs.

\-   RetailOps AI Backend never touches PostgreSQL directly — it calls StockPilot Core's API as tools, same as this frontend does.

\-   This frontend calls StockPilot Core directly for all business data, and calls RetailOps AI Backend directly (not through StockPilot Core) for the embedded AI sidebar, using the same JWT (see § Session Management).

\-   Two frontends, two Vercel projects, two independent deploy pipelines — a change to one never requires redeploying the other.



\## 2\\. System diagram



\# 



&#x20;                           ┌─────────────────────────┐

&#x20;                           │        End user          │

&#x20;                           └────────────┬─────────────┘

&#x20;                                        │

&#x20;                 ┌──────────────────────┼──────────────────────┐

&#x20;                 │                                              │

&#x20;     ┌───────────▼────────────┐                    ┌────────────▼───────────┐

&#x20;     │  StockPilot Frontend    │                    │   RetailOps AI          │

&#x20;     │  (this repo)            │                    │   Frontend (copilot)    │

&#x20;     │  Next.js 16 / React 19  │                    │   Next.js 16            │

&#x20;     │  stockpilot.<domain>    │                    │   ai.stockpilot.<domain>│

&#x20;     │  Vercel project A       │                    │   Vercel project B      │

&#x20;     └───────────┬────────────┘                    └────────────┬───────────┘

&#x20;                 │  REST (JWT)                        REST/SSE  │  (JWT)

&#x20;                 │                                              │

&#x20;     ┌───────────▼────────────┐   REST (server-to-server) ┌────▼───────────────┐

&#x20;     │   StockPilot Core       │◄───────────────────────────│  RetailOps AI       │

&#x20;     │   FastAPI                │       (tool calls)         │  Backend            │

&#x20;     │   Business APIs, Auth    │────────────────────────────►  LangGraph agents   │

&#x20;     │   Railway/Fly             │                             │  Railway/Fly        │

&#x20;     └───────────┬──────────────┘                             └─────────────────────┘

&#x20;                 │

&#x20;     ┌───────────▼────────────┐

&#x20;     │      PostgreSQL          │

&#x20;     └───────────────────────────┘

&#x20;   



\## 3\\. Folder structure



\# 



&#x20;   app/(auth)/...            → § Authentication Flow

&#x20;   app/(dashboard)/...       → one route segment per resource, see docs/PRODUCT-SPEC.md §24 for page-by-page detail

&#x20;   lib/api/                  → § API Architecture

&#x20;   lib/auth/                 → § Authentication Flow, § Session Management

&#x20;   lib/rbac/                 → § Authorization (RBAC)

&#x20;   lib/query/                → § State Management

&#x20;   components/ui/             → shadcn primitives, re-themed per docs/DESIGN-SPEC.md

&#x20;   components/data-table/     → shared table primitive

&#x20;   components/forms/           → shared form primitive + validation wiring

&#x20;   components/ai-sidebar/      → § AI Integration Architecture

&#x20;   contracts/                  → source of truth for every StockPilot Core endpoint this repo consumes; see § API Contracts

&#x20;   docs/

&#x20;     PRODUCT-SPEC.md

&#x20;     ARCHITECTURE.md            (this file)

&#x20;     DESIGN-SPEC.md

&#x20;     adr/

&#x20;   



Full engineering-level detail (one resource = one API module + one validation schema + one type file, no `any`, etc.) lives in `CLAUDE.md` — this section only maps structure to the architectural concerns below.



\## 4\\. API architecture



\# 



Every read/write in this app follows one of two shapes.



\*\*Server Component read (default):\*\*



&#x20;   Route Server Component

&#x20;     → lib/api/<resource>.ts (typed fetch, attaches auth header server-side)

&#x20;       → StockPilot Core REST endpoint

&#x20;         ← JSON response

&#x20;       ← validated via zod schema in lib/validation/<resource>.ts

&#x20;     ← rendered, or passed to a Client Component for interactivity

&#x20;   



\*\*Client mutation / interactive list:\*\*



&#x20;   User action (filter change, form submit, bulk action)

&#x20;     → hook in hooks/ calling lib/api/<resource>.ts

&#x20;       → centralized fetch wrapper (lib/api/client.ts)

&#x20;         - attaches Authorization: Bearer <jwt> (or relies on the shared cookie, see § Session Management)

&#x20;         - on 401: attempt refresh once, retry, else redirect to login

&#x20;         - normalizes error shape to a single AppError type

&#x20;       → StockPilot Core REST endpoint

&#x20;         ← JSON or structured error

&#x20;       ← zod-validated

&#x20;     ← client cache updated (§ State Management); affected queries/tags invalidated

&#x20;     ← UI re-renders from cache, optimistic update rolled back on failure

&#x20;   



\*\*Pagination/filter/sort convention\*\* (one shape, reused by every list endpoint): query params `page`, `pageSize`, `sort` (`field:asc|desc`), and `filter\[<field>]=<value>` — defined once in `lib/api/list-params.ts`, imported by every resource's list function. If StockPilot Core's actual convention differs, this file is the single place to adapt it.



\## 5\\. API contracts



\# 



`contracts/` is the source of truth for every endpoint this frontend consumes — one file (or OpenAPI-derived section) per resource: `contracts/auth.md`, `contracts/products.md`, `contracts/inventory.md`, `contracts/purchase-orders.md`, `contracts/ai-context.md`, etc. Each contract entry defines: method + path, request shape, response shape (mirrored by a zod schema in `lib/validation/`), error responses and their `AppError` mapping, and pagination/filter support if it's a list endpoint.



Rules:



\-   No `lib/api/` function is written against a guessed response shape — if a contract doesn't exist yet for an endpoint a task needs, that's a blocker to flag, not a shape to invent.

\-   If the live API is discovered to differ from a stale contract doc during implementation, the contract doc is corrected in the same PR — contracts describe reality, not aspiration.

\-   `contracts/ai-context.md` is the one contract owned jointly with the RetailOps AI side (see § AI Integration Architecture) — it's versioned, and a breaking change to it requires coordinated updates on both sides, not silent drift.



\## 6\\. Authentication flow



\# 



&#x20;   1. User submits credentials on /login

&#x20;   2. app/(auth)/login → lib/auth/login() → POST StockPilot Core /auth/login

&#x20;   3. StockPilot Core validates against Postgres, returns session credentials

&#x20;      (exact mechanism — token in body vs. Set-Cookie — per § Session Management)

&#x20;   4. lib/auth stores/reads the session per contracts/auth.md

&#x20;   5. Route guard (layout-level, app/(dashboard)/layout.tsx) checks session

&#x20;      validity on every protected navigation

&#x20;   6. On expiry: fetch wrapper (lib/api/client.ts) catches 401 →

&#x20;      attempt refresh →

&#x20;        success: retry original request once

&#x20;        failure: clear session, redirect to /login?redirect=<original path>

&#x20;   7. The same session is used for RetailOps AI Backend calls from the AI

&#x20;      sidebar — no second login (see § Session Management for how this is

&#x20;      actually achieved across the two frontend domains)

&#x20;   



\*\*Logout:\*\* clears local session state and calls StockPilot Core's logout endpoint if one exists (invalidate refresh token server-side) — verify against `contracts/auth.md` before assuming client-side clearing alone is sufficient.



\## 7\\. Authorization (RBAC)



\# 



Authentication (§6) establishes \_who\_ the user is; authorization determines \_what\_ they can see and do, per the roles defined in `docs/PRODUCT-SPEC.md` §6.



&#x20;   Permission source

&#x20;     → JWT claims (if StockPilot Core embeds role/permissions in the token), or

&#x20;     → GET /me/permissions (if permissions are fetched separately, e.g. because

&#x20;       they can change without requiring a new token)

&#x20;     → cached client-side for the session, re-fetched on session refresh

&#x20;   

&#x20;   Usage

&#x20;     → lib/rbac/ exposes useCan('resource:action') and a server-side equivalent

&#x20;       for route guards and Server Components

&#x20;     → components conditionally render/disable actions the current role can't

&#x20;       perform

&#x20;     → route segments requiring a specific permission are guarded at the

&#x20;       layout level (server-side check), not just hidden via client-side nav

&#x20;   



\*\*The frontend is never the sole enforcement point.\*\* Every mutating request assumes StockPilot Core re-checks permission server-side regardless of what the UI allowed the user to attempt — a hidden button is a UX convenience, not a security boundary. If a task requires a permission check that has no server-side equivalent yet, that's a gap to flag, not a client-only control to ship as if it were secure.



\## 8\\. State management



\# 



Two distinct state layers, used for different purposes — don't blur them:



\-   \*\*Server state (business data)\*\* — fetched via Server Components by default (§4), or via a client-side query library for interactive lists and post-load mutations. Cache keys are scoped per resource and per query params (list filters included), so two different filtered views of Inventory don't collide in cache. After any mutation, exactly the affected queries are invalidated — never a full-page reload to "make sure it's fresh," and never an invalidation broad enough to refetch unrelated resources.

\-   \*\*Client/UI state (ephemeral)\*\* — form input before submit, table column visibility, sidebar open/closed, current AI conversation within a session. Lives in component state or a lightweight client store; never persisted as if it were business data, and never the source of truth for anything also held server-side.



Optimistic updates are used only where the mutation is low-risk and the rollback path is well-defined (e.g. marking a notification read); anything with real business consequence (PO status transitions, stock receipt) waits for server confirmation before reflecting success in the UI.



\## 9\\. Server Components and Client Components



\# 



\-   React Server Components are the default for every route. `'use client'` is added only where interactivity, local state, or a browser API is required — pushed as far down the component tree as possible, never applied to a whole page just because one child needs it.

\-   Data fetching for the initial render of a page happens in Server Components wherever the data doesn't need post-load interactivity (detail pages, most of Dashboard).

\-   Client Components own: search/filter/sort interactions on list pages, forms, the data-table primitive's interactive chrome, the AI sidebar, anything using the state layer in §8's second bullet.

\-   Suspense boundaries and `loading.tsx` per route segment implement the loading-state requirement from `docs/PRODUCT-SPEC.md` at the routing level, not only inside individual components.

\-   Route-level `error.tsx` per segment, not a single global catch-all — see § Error Handling Architecture.



\## 10\\. Error handling architecture



\# 



&#x20;   StockPilot Core error response

&#x20;     → lib/api/client.ts normalizes to AppError { kind, message, fields? }

&#x20;       kind ∈ { 'network', 'auth', 'validation', 'business-rule', 'server', 'unknown' }

&#x20;     → thrown or returned per call site convention (mutations: returned in a

&#x20;       result type; reads: thrown, caught by nearest error.tsx boundary)

&#x20;     → UI renders per kind, per the voice and content rules in

&#x20;       docs/PRODUCT-SPEC.md §17:

&#x20;         network       → retry affordance

&#x20;         auth          → redirect to login (handled in client.ts before

&#x20;                          reaching the component)

&#x20;         validation    → field-level messages in the form

&#x20;         business-rule → specific message surfaced from the API's own reason

&#x20;         server/unknown→ specific-but-generic message + an error ID

&#x20;                          cross-referenced to the monitoring system (§14)

&#x20;   



Route-level `error.tsx` per segment catches anything that escapes a component boundary; it never shows a raw stack trace to the user, but does surface an error ID mapped to the corresponding monitoring event.



\## 11\\. AI integration architecture



\# 



&#x20;   User          Frontend               RetailOps AI Backend        StockPilot Core

&#x20;    │ click "Explain" on a  │                    │                        │

&#x20;    │ Dashboard KPI          │                    │                        │

&#x20;    │──────────────────────►│                    │                        │

&#x20;    │                        │ POST /agent/query  │                        │

&#x20;    │                        │ { query, context: { page, resourceType,     │

&#x20;    │                        │   resourceId?, period? } }                   │

&#x20;    │                        │───────────────────►│                        │

&#x20;    │                        │                    │  Planner → sub-agents  │

&#x20;    │                        │                    │  call tools            │

&#x20;    │                        │                    │───────────────────────►│

&#x20;    │                        │                    │  ◄── tool results      │

&#x20;    │                        │                    │◄───────────────────────│

&#x20;    │                        │  ◄── SSE stream: partial text + citations   │

&#x20;    │                        │◄───────────────────│                        │

&#x20;    │◄───────────────────────│ sidebar renders streamed answer +           │

&#x20;    │  citation chips open   │ citation chips (shared component, see below)│

&#x20;    │  the provenance drawer │                                             │

&#x20;   



\-   The AI sidebar is a Client Component mounted once in `app/(dashboard)/layout.tsx`, persistent across route navigation within a session.

\-   \*\*Context-passing contract:\*\* every query includes route, resource type, resource ID if on a detail page, and visible time period if relevant. Defined and versioned in `contracts/ai-context.md` (§5).

\-   \*\*Component reuse decision (needs an ADR before Stage 10):\*\* citation chip, provenance drawer, and recommendation card components are either (a) a shared package consumed by both frontends, or (b) deliberately duplicated and tracked with an explicit sync process. Pick one and record it in `docs/adr/` — letting it happen by accident risks the two UIs drifting apart on the exact pattern meant to establish trust.

\-   \*\*Streaming:\*\* SSE from RetailOps AI Backend; partial markdown/tables buffer until they close cleanly, matching the copilot's own behavior.

\-   \*\*Recommendations surfaced inline\*\* (e.g. on Inventory Details) are fetched from RetailOps AI Backend scoped to that resource, cached independently of StockPilot Core business data — accepting/rejecting updates RetailOps AI's own recommendation log, never anything in StockPilot Core directly.



\## 12\\. Data flow



\# 



Three data categories flow through this app differently:



1\.  \*\*Business data\*\* (Products, Inventory, Suppliers, POs, Sales) — read/ write directly against StockPilot Core, cached per §8, invalidated precisely on mutation.

2\.  \*\*Derived/computed display data\*\* (margins, KPI deltas, ABC classifications if computed client-side) — computed from #1, never persisted, always recomputed from the current cache, labeled per the provenance pattern in `docs/PRODUCT-SPEC.md` §13 wherever visible.

3\.  \*\*AI-sourced data\*\* (recommendations, explanations) — flows from RetailOps AI Backend independently of #1 and #2; never conflated with business data — always rendered inside the citation-chip pattern.



\## 13\\. Component communication



\# 



\-   \*\*Server → Client:\*\* Server Components pass fetched data down as props to Client Component boundaries; no client-side re-fetch of data the server already resolved for that render.

\-   \*\*Sibling Client Components on the same page\*\* (e.g. a filter bar and the table it filters) communicate through the shared query state in §8 (URL-reflected filter params), not through prop-drilling or ad hoc context created per page — one filter-state pattern, reused everywhere a list page needs it.

\-   \*\*Cross-cutting concerns\*\* (auth session, current user/role, AI sidebar open state) live in a small number of top-level providers mounted in the root/dashboard layout — not re-created per page.

\-   \*\*Frontend ↔ backend\*\* communication is exclusively HTTP/SSE per §4 and §11 — no direct database access, no WebSocket layer in the initial scope (real-time collaborative editing is future roadmap, see `docs/PRODUCT-SPEC.md` §25).



\## 14\\. Deployment strategy and diagram



\# 



&#x20;                       ┌────────────────────┐

&#x20;      git push main ──►│  GitHub repo         │

&#x20;                       └─────────┬───────────┘

&#x20;                                 │ webhook

&#x20;                       ┌─────────▼───────────┐

&#x20;                       │  Vercel (Project A:   │

&#x20;                       │  StockPilot Frontend) │

&#x20;                       │  - preview per PR     │

&#x20;                       │  - production on main │

&#x20;                       │  - stockpilot.<domain>│

&#x20;                       └─────────┬───────────┘

&#x20;                                 │ env vars: see § Environment Variables

&#x20;                                 ▼

&#x20;                       (calls StockPilot Core + RetailOps AI Backend at

&#x20;                        runtime, both deployed independently — § 1)

&#x20;   



RetailOps AI Frontend deploys identically as \*\*Project B\*\* (`ai.stockpilot.<domain>`), with its own env vars pointing at RetailOps AI Backend. The two frontend Vercel projects share nothing at deploy time — no shared build, no shared env — they only share the `docs/DESIGN-SPEC.md` token file, duplicated (not symlinked) into each repo and kept in sync manually or via a shared package if that becomes worth the overhead (flag as an ADR if pursued).



\*\*Domain scheme:\*\* `stockpilot.<domain>` for the ERP, `ai.stockpilot.<domain>` for the copilot, both under Vercel custom domains on the same root — presenting one product family rather than two unrelated apps. This depends on § Session Management to deliver a real shared login, not just matching branding.



\## 15\\. Session management



\# 



`localStorage`\\-based token storage is origin-scoped and will \*\*not\*\* share a session across `stockpilot.<domain>` and `ai.stockpilot.<domain>` — each app would silently require its own login, contradicting the one-platform goal in `docs/PRODUCT-SPEC.md` §2/§9. To get real shared session:



\-   StockPilot Core must issue the session as an `httpOnly`, `Secure` cookie with `Domain=.stockpilot.<domain>` (leading dot) at login, not just return a token in the response body for the frontend to store itself.

\-   Both frontends read auth state via a cookie-forwarded request (or a `/me` check on load) rather than pulling a token out of client storage.

\-   This is a \*\*backend-owned decision\*\* — neither frontend repo can retrofit it unilaterally. Confirm with StockPilot Core's auth implementation before Stage 0 writes `lib/auth/`, and record the outcome as an ADR in both frontend repos, since it changes the auth contract both consume.

\-   \*\*Fallback if unsupported in the sprint timeframe:\*\* two independent logins on matching shared-looking chrome — acceptable, but must be a stated, deliberate limitation in both READMEs, not a silent gap discovered by a confused user later.



\## 16\\. Security architecture



\# 



\-   \*\*Transport:\*\* HTTPS everywhere, no plaintext fallback, enforced at the Vercel/edge level.

\-   \*\*Session:\*\* per § Session Management — httpOnly cookie preferred over client-readable token storage specifically to reduce XSS token-theft exposure.

\-   \*\*Authorization:\*\* per § Authorization (RBAC) — server is always the final authority, never the client.

\-   \*\*Input validation:\*\* every form submission and API response is validated (zod) at the boundary — the frontend never trusts an unvalidated shape from either the user or the network.

\-   \*\*Secrets:\*\* no secret is ever exposed to client-side code; anything server-only (build-time tokens, source-map upload credentials) is scoped to server/build environment variables only — see § Environment Variables.

\-   \*\*CORS:\*\* StockPilot Core and RetailOps AI Backend allow only the known frontend origins (`stockpilot.<domain>`, `ai.stockpilot.<domain>`, and their Vercel preview URLs) — this is backend-owned configuration, noted here because both frontends depend on it being correct or preview deployments will silently fail to call the API.



\## 17\\. Environment variables



\# 



| Variable | Where used | Notes |

| --- | --- | --- |

| `NEXT\_PUBLIC\_API\_BASE\_URL` | `lib/api/client.ts` | StockPilot Core base URL |

| `NEXT\_PUBLIC\_AI\_BASE\_URL` | `components/ai-sidebar/` | RetailOps AI Backend base URL |

| `NEXT\_PUBLIC\_APP\_URL` | cross-app links (e.g. Dashboard → open full AI app) | `https://stockpilot.<domain>` or `https://ai.stockpilot.<domain>`, set per project |

| `AUTH\_COOKIE\_DOMAIN` | StockPilot Core only (not this frontend) | `.stockpilot.<domain>` — listed here for visibility since both frontends depend on it, see § Session Management |

| `NEXT\_PUBLIC\_SENTRY\_DSN` | error tracking init | client-side |

| `SENTRY\_AUTH\_TOKEN` | build-time only | source map upload, never exposed client-side |

| `NODE\_ENV` | framework-managed | — |



Real values live in Vercel's environment settings per project (Preview vs. Production scoped separately). `.env.example` in the repo lists every key with a placeholder, never a real value. Update this table whenever a new env var is introduced.



\## 18\\. CI/CD pipeline



\# 



&#x20;   PR opened/updated

&#x20;     → GitHub Actions: lint, type-check, unit tests, integration tests, axe-core a11y

&#x20;     → Vercel: preview deployment

&#x20;     → Playwright E2E against the preview URL (from the stage that introduces it — see BUILD.md)

&#x20;     → Lighthouse CI against the preview URL (Dashboard, Inventory routes)

&#x20;     → all green required before merge (branch protection)

&#x20;   

&#x20;   Merge to main

&#x20;     → GitHub Actions: full suite again

&#x20;     → Vercel: production deployment

&#x20;     → Monitoring release marker created, source maps uploaded

&#x20;     → smoke E2E run against production URL

&#x20;   



No manual deploy step for routine changes. A failing check blocks merge; there is no "merge anyway" path for main.



\## 19\\. Monitoring and logging



\# 



\-   \*\*Error tracking:\*\* wired from the earliest build stage, not deferred to launch — client and server side.

\-   \*\*Performance monitoring:\*\* real-user LCP/INP/CLS on the Dashboard and Inventory routes, checked against the budgets in `CLAUDE.md`.

\-   \*\*Structured logging:\*\* client-side errors include route, user role (never PII beyond what's already in session claims), and the `AppError` `kind` from §10 — enough to triage without needing to reproduce.

\-   \*\*Uptime:\*\* an external check against both this frontend and StockPilot Core's health endpoint, since this frontend is non-functional if that dependency is down — monitoring should make that dependency visible.

\-   \*\*Audit log vs. system logs — not the same thing.\*\* The in-app Audit Log page (`docs/PRODUCT-SPEC.md` FR-12) is a business feature sourced from StockPilot Core. Monitoring/logging in this section is operational visibility into this frontend's own health. Different audiences, different systems.



\## 20\\. Performance strategy



\# 



\-   Route-level JS and LCP budgets: defined and enforced per `CLAUDE.md` (kept there since it's an engineering gate, not an architectural decision) — this section notes the architectural levers used to hit them: Server Component-first data fetching (§9) to minimize client JS, table virtualization for large lists (§ Caching Strategy), and route- level code-splitting via the App Router's natural boundaries.

\-   Images served via `next/image`; no unoptimized `<img>` for API-sourced content.



\## 21\\. Caching strategy



\# 



\-   Server Component fetches use Next.js's built-in fetch caching with explicit revalidation (time-based or on-demand via tag/path revalidation after a mutation) — cache behavior is always explicit, never left to framework defaults unexamined.

\-   List views with search/filter/sort use the client-side query cache from §8 for request dedup, background refetch, and optimistic updates on low-risk mutations.

\-   After any mutation, exactly the affected queries/tags are invalidated — never a broader invalidation than the mutation's actual blast radius.

\-   Data tables virtualize past \~200 rows — never render an unbounded row set into the DOM regardless of cache state.



\## 22\\. Scaling strategy



\# 



This is a portfolio/demo-scale app against a bounded dataset (\~5,243 products, \~1M historical transactions), so scaling strategy here is mostly about \*\*not writing code that would fall over if scope grew\*\*, rather than provisioning for real load:



\-   Server-side pagination and table virtualization from day one (§21) is the single highest-leverage decision — there's no "add pagination later" debt because it's required at small scale already.

\-   Vercel's serverless/edge model scales the frontend automatically — no server capacity planning needed on this side.

\-   StockPilot Core is the real bottleneck if this ever needed to scale — this frontend's job is to not make that worse (no N+1 client-side fetch waterfalls, no unbounded list fetches, request dedup per §21).

\-   Caching headroom: if this became a real multi-tenant product, the next step would be a shared edge cache in front of StockPilot Core itself — out of scope for this repo, noted here so the boundary is clear.



\## 23\\. Future scalability considerations



\# 



\-   \*\*Multi-tenancy is not built.\*\* If it's ever needed, it changes the auth flow (§6), every list query (tenant-scoping), and RBAC (§7), and should be an ADR and a `CLAUDE.md` revision before any code changes, not a quiet retrofit.

\-   \*\*A shared component package\*\* between the two frontends (see §11's ADR requirement) becomes more valuable the more the two UIs need to stay in lockstep — if drift becomes a recurring problem, that's the trigger to revisit duplication-with-sync in favor of an actual shared package.

\-   \*\*A real-time layer\*\* (WebSockets, e.g. for live collaborative PO editing) is deliberately deferred — see `docs/PRODUCT-SPEC.md` §25 — and would introduce a new architectural pattern (persistent connections, presence state) not covered by anything in this document today; it needs its own ADR if pursued.

\-   \*\*Native mobile\*\* would likely mean a shared API/contract layer reused by a React Native or platform-native client, not a rebuild of business logic — noted here so a future decision starts from "reuse contracts/" rather than from scratch.



\## Keeping this document honest



\# 



Update this file when an actual architectural decision is made or changes — a new service, a changed auth flow, a new env var, a scaling decision. Don't let it drift into aspirational documentation: if a diagram here doesn't match what's deployed, fix the diagram or fix the deployment in the same PR. Task-level detail belongs in `BUILD.md`; rationale for a specific choice belongs in `docs/adr/`; this file is the map, not the diary.

