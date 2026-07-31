# CLAUDE.md — StockPilot Frontend (ERP)

# 

Read by Claude Code at the start of every session in this repo. This is the standing engineering contract for the **StockPilot Frontend** — the business application. It is a separate repo, separate Vercel deployment, and separate codebase from **RetailOps AI** (the AI Copilot frontend). Do not merge them.

## Documentation hierarchy

# 

Four documents, each with one job — don't duplicate content across them:

-   **`docs/PRODUCT-SPEC.md`** — _what_ we build: vision, roles, journeys, functional/non-functional requirements, page-by-page behavior, business rules. Product behavior questions go here first.
-   **`docs/ARCHITECTURE.md`** — _how the system is designed_: diagrams, API contracts, auth/session/RBAC mechanics, state management, deployment, monitoring, scaling. Technical-design questions go here first.
-   **`BUILD.md`** — _in what order_ we build it: phased stages, checkpoints, per-stage acceptance criteria and tests.
-   **This file (`CLAUDE.md`)** — engineering rules, coding standards, testing rules, quality gates, Definition of Done, and day-to-day development workflow. It assumes you already know _what_ and _how_ from the two docs above, and tells you the standard the code itself must meet.

If you're unsure whether something belongs here or in `docs/ARCHITECTURE.md` or `docs/PRODUCT-SPEC.md`: rules about how code is written belong here; everything else belongs in one of the other two.

* * *

## 1\. System context

# 

Full system architecture, diagrams, and service boundaries are in `docs/ARCHITECTURE.md` §1–2 — read that before touching anything cross-service. The rules that follow from it, restated here because they constrain how code in _this_ repo is written:

-   This repo never touches PostgreSQL and never imports a backend ORM model. Business data comes exclusively through StockPilot Core's REST API, defined in `contracts/` (`docs/ARCHITECTURE.md` § API Contracts).
-   StockPilot Core owns auth. This repo consumes the session it issues; it does not implement its own login logic beyond calling the auth endpoint and reading/storing the session per `docs/ARCHITECTURE.md` § Session Management.
-   The AI Copilot is embedded here as a **sidebar surface** (Stage 10), not reimplemented. It calls RetailOps AI Backend directly from this frontend — that is the one exception to "only talk to StockPilot Core" and it's deliberate; see `docs/ARCHITECTURE.md` § AI Integration Architecture for the contract.
-   If a task seems to require a new StockPilot Core endpoint that doesn't exist in `contracts/`, stop and flag it — don't invent a response shape or fetch from a guessed URL.

## 2\. Design system

# 

Shared with RetailOps AI via `docs/DESIGN-SPEC.md` in this repo (ported from the copilot project, not diverged). Every color, type size, spacing, and radius value used in code must trace to a token defined there. The ERP adds new component patterns (data tables, forms, wizards, status workflows) that aren't in the original spec — when you need one that isn't covered, extend `docs/DESIGN-SPEC.md` with a new named token/pattern and note the addition in your session close-out; don't invent a one-off value inline.

Non-negotiable subset:

-   Numerics (currency, IDs, SKUs, quantities, timestamps) render in Geist Mono with `font-variant-numeric: tabular-nums`. Prose and labels in Geist Sans.
-   One accent color for interactive state; no second accent; no gradients, glow, or card shadows.
-   Status is never color-only — every status pill carries text.
-   Currency is £. This is a UK dataset end to end.
-   6px radius, 8px spacing rhythm, hairline borders — same as the copilot.

The bar stated in the brief — Fiori, NetSuite, Dynamics, Odoo Enterprise, Stripe Dashboard, Linear, Vercel Dashboard, GitHub — is a **density and precision** bar, not a decoration bar. Those products win on: information density without clutter, instant perceived performance, keyboard-first power-user flows, and restraint. None of them use gradients, glow, or decorative color. Match them on those axes, not on visual richness.

## 3\. Folder structure

# 

    app/
      (auth)/
        login/
        ...
      (dashboard)/
        dashboard/
        products/
          [id]/
        inventory/
          [id]/
        suppliers/
          [id]/
        purchase-orders/
          [id]/
        sales/
          orders/
          customers/
        forecasts/
        analytics/
        reports/
        notifications/
        audit-logs/
        settings/
          users/
          roles/
          api-keys/
          profile/
        layout.tsx        # shell: nav, header, AI sidebar mount point
    components/
      ui/                 # shadcn primitives, re-themed
      data-table/          # shared table primitive: sort, filter, paginate, export, bulk actions
      forms/               # shared form primitives + validation wiring
      charts/               # Recharts wrappers per chart type used
      layout/               # nav, header, page shell, breadcrumb
      ai-sidebar/            # RetailOps AI embed
    lib/
      api/                  # typed client per StockPilot Core resource, generated or hand-written from contracts/
      auth/                 # token storage, refresh, route guards
      validation/            # zod schemas, one per resource, shared by forms and API layer
      rbac/                  # permission checks, role gating
    hooks/
    types/
      api/                  # types generated/derived from contracts/, never hand-duplicated
    contracts/                # OpenAPI or hand-written contract docs for every StockPilot Core endpoint consumed — see docs/ARCHITECTURE.md § API Contracts
    docs/
      PRODUCT-SPEC.md
      ARCHITECTURE.md
      DESIGN-SPEC.md
      adr/                   # architecture decision records for this repo
    tests/
      unit/
      integration/
      e2e/                    # Playwright
    

One resource = one API module + one validation schema + one type file. Don't scatter a resource's logic across three ad hoc locations. The set of resources and pages this folder structure needs to support is defined in `docs/PRODUCT-SPEC.md` §24 — check there before adding or renaming a route segment.

## 4\. TypeScript rules

# 

-   Strict mode, no exceptions. `noImplicitAny`, `strictNullChecks` on.
-   No `any`. If a type is genuinely unknown at a boundary, use `unknown` and narrow it — don't silence the checker.
-   Every API response is validated at the boundary (zod) before it's typed as trusted data. A component never receives an unvalidated network response.
-   No type duplication between `types/api/` and `lib/validation/` — derive one from the other (`z.infer<typeof schema>`), don't hand-write both.
-   Discriminated unions for state, not boolean flag soup (`status: 'idle' | 'loading' | 'error' | 'success'`, not `isLoading` + `isError` + `hasData` as independent booleans that can contradict each other).

## 5\. React / Next.js rules

# 

The Server/Client Component split and the Suspense/error-boundary routing pattern are architectural decisions defined in `docs/ARCHITECTURE.md` § Server Components and Client Components — read that first. Coding rules that implement it:

-   No `useEffect` for data fetching that could be a server fetch. If you reach for `useEffect`, justify why it isn't a server component, a server action, or a derived value first.
-   Server Actions for mutations (create/update/delete) where the framework supports it cleanly; fall back to a typed API client call otherwise — pick one pattern per mutation type and stay consistent across resources.
-   `'use client'` is pushed as far down the tree as possible — never applied to a whole page file because one child needs interactivity.

## 6\. Component structure

# 

-   One component per file, colocated test file (`Component.tsx`, `Component.test.tsx`).
-   Presentational components take data as props and render; they don't fetch. Fetching/mutation logic lives in a hook or the server component above them.
-   Shared primitives (`data-table`, `forms`) are configuration-driven — a new resource's table or form is built by passing column/field config into the shared primitive, not by copy-pasting a table component per resource. This is the difference between 15 pages that feel like one product and 15 pages that feel hand-cloned.
-   No component exceeds ~200 lines before it's split. If a page component is mostly layout + composition of smaller pieces, that's correct; if it's 400 lines of inline JSX and logic, it isn't.

## 7\. API layer

# 

Full request/response flow and the AppError taxonomy are in `docs/ARCHITECTURE.md` § API Architecture and § Error Handling Architecture. Coding rules that implement it:

-   One typed client function per endpoint, generated from or checked against `contracts/` — request params, body, and response all typed.
-   No endpoint URL string literals scattered through components — they live in the API layer only.
-   Pagination, sorting, and filtering params follow the one convention defined in `lib/api/list-params.ts` — don't let a resource invent its own query-param shape.

## 8\. Error handling

# 

Voice and content rules for what an error says are in `docs/PRODUCT-SPEC.md` §17; the `AppError` taxonomy and routing logic are in `docs/ARCHITECTURE.md` § Error Handling Architecture. The coding rule: every mutation (create/update/delete, PO receive, bulk action) implements an in-flight state, a specific success confirmation, and a specific failure message — no mutation ships with only a happy path.

## 9\. Caching

# 

Caching architecture (Server Component fetch caching, client query cache, invalidation scope) is defined in `docs/ARCHITECTURE.md` § State Management and § Caching Strategy. The coding rule: don't hand-roll fetch-and-`useState` for anything with pagination — use the query library per that section, and invalidate exactly the queries/tags a mutation affects, never a broader refetch than that.

## 10\. Performance budgets

# 

-   Route-level JS (uncompressed) target: dashboard and list pages < 180KB, detail/form pages < 220KB. Flag it if a route exceeds this and identify what's pulling weight before adding more.
-   Largest Contentful Paint target < 2.0s on a throttled 4G profile for the Dashboard and Inventory list (the two highest-traffic routes).
-   Data tables virtualize past ~200 rows — never render an unbounded row set into the DOM.
-   Images (product images) served via `next/image`, no unoptimized `<img>` for anything from the API.
-   No client-side chart library import in a Server Component tree that doesn't render a chart — verify bundle impact per route before merging a new chart type.

## 11\. Accessibility

# 

The requirement bar (WCAG 2.1 AA floor, contrast ratios, keyboard operability, icon-label and color-independent-status rules) is defined in `docs/PRODUCT-SPEC.md` §22 — read that first. Coding rules that implement it:

-   Forms: associate every error with its field via `aria-describedby`, announce validation errors on submit — don't just satisfy the contrast/label requirement and skip the announcement.
-   Data tables: proper `<table>` semantics or ARIA grid pattern if using a non-native table component.
-   Verify with a manual screen-reader spot-check on the Inventory and Purchase Order tables specifically (the densest surfaces) — automated axe-core in CI (§13) catches the rest, but not everything a screen reader user hits.
-   Contrast is checked per page, not assumed from the token file alone — context (overlays, states) can shift effective contrast below the §22 floor even when the token itself is compliant.

## 12\. Authentication & authorization (RBAC)

# 

Session mechanics (how the session is issued, stored, and shared across the two frontend domains) are in `docs/ARCHITECTURE.md` § Authentication Flow and § Session Management. The permission model and role definitions are in `docs/ARCHITECTURE.md` § Authorization (RBAC) and `docs/PRODUCT-SPEC.md` §6. Coding rules that implement them:

-   This repo does not invent a session storage mechanism ad hoc — check `contracts/auth.md` and `docs/ARCHITECTURE.md` § Session Management before writing any auth code.
-   Route guards at the layout level per protected segment; redirect to login on missing/expired session, preserving the intended destination for post-login redirect.
-   Role/permission checks are **UI-level only** — they hide/disable actions a user shouldn't see, but the frontend must never be the sole enforcement point. Every mutating action assumes the backend re-checks permission.
-   Permission checks are centralized in `lib/rbac/`, called from components as a hook (`useCan('purchase_order:receive')`), not re-implemented as scattered role-name string comparisons.

## 13\. Testing strategy

# 

-   Unit: pure functions, validation schemas, RBAC logic, formatting utils (currency, date, provenance-adjacent formatting shared with the copilot).
-   Integration: data-table primitive (sort/filter/paginate/export/bulk), form primitive (validation, submit, error display), API client (mocked network layer against `contracts/` shapes).
-   E2E (Playwright): one full happy-path flow per major resource (create a product, receive a purchase order, run a forecast view, invite a user) plus the cross-cutting flows (login → dashboard, AI sidebar open from three different pages).
-   Accessibility: automated axe-core pass on every route in CI, plus the manual screen-reader spot-checks called out in §11.
-   No stage in `BUILD.md` is marked done without its listed tests passing — see that file's per-stage test requirements.

## 14\. Git workflow & commit policy

# 

-   One commit per checkpoint defined in `BUILD.md`, not one commit per file and not one commit per stage.
-   Commit messages: `type(scope): summary` — `feat(inventory): add table with server-side pagination`, `fix(auth): refresh token race on tab focus`. Scope matches the resource/folder.
-   No commit lands with failing lint, failing type-check, or failing tests for the area touched.
-   Feature branches per stage, merged via PR even if reviewing solo — PR description states what was built and links the `BUILD.md` checkpoint it satisfies. This is a portfolio artifact; the commit history and PR log are part of what a reviewer reads.

## 15\. Documentation policy

# 

-   Every ADR-worthy decision (state management choice, data-table library choice, RBAC model, why a particular caching strategy) gets a short ADR in `docs/adr/`, not just a Slack-style comment in code.
-   `contracts/` is kept in sync with the backend as endpoints are consumed — if you discover the live API differs from a stale contract doc, update the doc in the same PR, don't just code against reality and leave docs wrong.
-   If a build task reveals that `docs/PRODUCT-SPEC.md` or `docs/ARCHITECTURE.md` is wrong or out of date, fix the doc in the same PR — these are living references, not one-time specs, and a stale architecture diagram is worse than none.
-   README covers: what this app is, how it relates to StockPilot Core and RetailOps AI, local setup, environment variables, how to run tests, and a link to the deployed instance once Stage 12 ships.

## 16\. Deployment checklist (detailed in BUILD.md Stage 12)

# 

Summarized here as a standing bar, not a one-time task:

-   Environment variables documented in `.env.example`, none committed as real secrets.
-   Production build has no console errors/warnings on a full click-through.
-   Error tracking wired (Sentry or equivalent) before calling any stage "production" — a production app without error visibility isn't production.
-   Preview deployments on every PR (Vercel default) used for review before merge to main.

## 17\. Definition of Done

# 

A stage, page, or component is not done until:

-   \[ \] It matches `docs/DESIGN-SPEC.md` tokens exactly — no ad hoc values
-   \[ \] It matches the behavior specified for it in `docs/PRODUCT-SPEC.md` (§24 page spec, relevant FRs, business rules) — not a superset or subset of what was actually asked for
-   \[ \] TypeScript strict, no `any`, API responses validated at the boundary
-   \[ \] Loading, empty, error states implemented (see §8) — not just the happy path
-   \[ \] Full keyboard operability, visible focus, screen-reader sanity check
-   \[ \] Tests specified for that unit in `BUILD.md` are written and passing
-   \[ \] RBAC-gated where relevant, gating verified for at least one denied role in addition to an allowed one
-   \[ \] Committed at a checkpoint per §14, not left as an uncommitted pile
-   \[ \] Session close-out reports status honestly against the `BUILD.md` checkbox — partial and blocked are acceptable answers, a false "done" is not

## 18\. What to do when something is ambiguous

# 

Don't invent an API shape, a permission model, a design token, or a product behavior to keep moving. Check `contracts/`, `docs/DESIGN-SPEC.md`, `docs/ARCHITECTURE.md`, and `docs/PRODUCT-SPEC.md` first; if the answer isn't there, stop and ask rather than guessing quietly. This repo holds itself to the same evidentiary standard the RetailOps AI product enforces on itself — a frontend that fabricates its own shortcuts undercuts the credibility of a product whose entire pitch is "nothing here is fabricated."