# BUILD.md — StockPilot Frontend (ERP) Implementation Roadmap

This is the complete roadmap for the StockPilot ERP frontend — _in what order_ it gets built. For _what_ to build, see `docs/PRODUCT-SPEC.md`; for _how the system is designed_, see `docs/ARCHITECTURE.md`; for engineering rules and quality gates that apply to every stage, see `CLAUDE.md` — read that first. This file's job is sequencing and per-stage checkpoints, not restating requirements or design decisions already covered in those docs.

## Scope reality check — read this before assigning a timeline

Stages 0–2 are a realistic scope for a 2–3 week solo sprint. Stages 3–9 are, at production quality with the testing and RBAC bar this doc sets, more realistically 2–3 months of additional work. This isn't a reason to shrink the spec — it's written in full below because a documented roadmap is itself a legitimate portfolio artifact — but don't schedule Stage 9 for next Tuesday. Two honest ways to run this:

-   **Ship-thin:** build Stages 0–2 (and Stage 10's AI sidebar, since it's the actual differentiator) to full production quality for the sprint, leave 3–9 and 11–12 as this written roadmap plus a couple of pages built to "structural, not fully wired" depth, and say exactly that in the README.
-   **Ship-long:** treat this as a multi-month build and work the stages in order at real depth.

Pick one and say so before starting Stage 0 — it changes how much depth Stage 0's shared primitives (data table, form system) need up front, since ship-thin only needs them robust enough for 2 resources, ship-long needs them robust enough for 12.

**The cut line below marks where "sprint" scope ends if you go ship-thin.**

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done, verified

* * *

## Stage 0 — Project bootstrap, architecture, authentication, layout

**Goals:** a running, deployed shell with real auth and no page content yet, proving the architecture end to end before any business logic is built.

**Tasks**

-   \[ \] Next.js 16 + React 19 + TypeScript strict scaffold
-   \[ \] Tailwind v4 via `@theme`; `docs/DESIGN-SPEC.md` ported from the RetailOps AI repo, tokens verified identical (shared brand)
-   \[ \] shadcn/ui installed, base theme overridden to match tokens before any component is used
-   \[ \] `contracts/` populated against the live StockPilot Core API (or its OpenAPI export) — auth, and at minimum the endpoint list for Stages 1–2, documented before those stages start
-   \[ \] Session management mechanism confirmed with the StockPilot Core backend before writing `lib/auth/` — see `docs/ARCHITECTURE.md` § Session Management for the required mechanism and its fallback
-   \[ \] Auth: login page, session storage/refresh per `contracts/auth.md` and the decision above, route guards on the `(dashboard)` segment group
-   \[ \] App shell: top nav, left nav (route list per §3 of CLAUDE.md), header with user menu, breadcrumb slot, AI sidebar mount point (empty until Stage 10)
-   \[ \] Shared primitives scaffolded: `data-table/`, `forms/`, `charts/` wrappers — built against one dummy resource first, not yet wired to real endpoints
-   \[ \] CI: lint, type-check, unit test run on every PR
-   \[ \] Error tracking wired (Sentry or equivalent) from day one, not deferred to Stage 12

**Acceptance criteria**

-   Logging in with valid StockPilot Core credentials lands on an empty dashboard shell; invalid credentials show a specific error; an expired token redirects to login and returns to the original route after re-auth.
-   Every nav item routes to a real (empty-state) page — no 404s in the primary nav.
-   `npm run build` is clean; CI is green.

**Tests**

-   Unit: token storage/refresh logic, RBAC hook stub.
-   Integration: login flow (success, failure, expired-token redirect).
-   E2E: login → land on dashboard → logout → redirected to login.

**Commit checkpoint:** `chore: bootstrap — auth, shell, shared primitives`

* * *

## Stage 1 — Dashboard

**Goals:** the landing page a user sees every day — status at a glance, not a wall of charts.

**Tasks**

-   \[ \] KPI cards: revenue (period-over-period), inventory value, low-stock count, open purchase orders — each a citation-style figure sourced from a real endpoint, not computed client-side from a list fetch
-   \[ \] Revenue chart (Recharts) — time series with period selector
-   \[ \] Inventory value chart or breakdown (by category or warehouse per `contracts/`)
-   \[ \] Low-stock panel — top N products under threshold, linking to Inventory detail
-   \[ \] Activity feed — recent orders, receipts, and (once Stage 10 exists) AI recommendations acted on; build the feed component now, wire the AI-sourced item type later
-   \[ \] Loading skeletons matching final KPI card and chart layout; empty states for a tenant with no data yet

**Acceptance criteria**

-   Every KPI figure and chart is backed by a real `contracts/`\-defined endpoint response, not a mock left in place.
-   Dashboard LCP < 2.0s on a throttled 4G profile (CLAUDE.md §10).
-   Fully responsive at 1280px and 768px.

**Tests**

-   Unit: KPI formatting (currency, percentage-change) utilities.
-   Integration: dashboard renders correctly across loading/empty/populated/ error states for each panel.
-   E2E: dashboard loads and each KPI card links to its detail page.

**Commit checkpoint:** `feat(dashboard): KPI cards, revenue/inventory charts, activity feed`

* * *

## Stage 2 — Inventory

**Goals:** the highest-traffic resource in the app — a genuinely usable dense table, not a demo table.

**Tasks**

-   \[ \] Inventory table via the shared `data-table` primitive: server-side pagination, sort, and filter (not client-side over a full fetch)
-   \[ \] Search (debounced, server-side)
-   \[ \] Filters: category, warehouse/location, stock status (low/ok/ overstock), supplier
-   \[ \] Warehouse/location support — if StockPilot Core models multiple locations, the table and filters reflect it; if not, flag the contract gap rather than inventing a location model client-side
-   \[ \] Pagination (page-size selector, server-driven)
-   \[ \] Export (CSV at minimum) of the current filtered/sorted view
-   \[ \] Bulk actions (e.g. bulk reorder-flag, bulk export selection) with a confirm step and a specific success/failure summary, not a silent no-op on partial failure
-   \[ \] Inventory Details page: single-item view — stock history, current levels per location, linked supplier(s), linked forecast if available

**Acceptance criteria**

-   Table performs acceptably (no visible jank) at realistic dataset size — test against the actual ~5,243 product catalog, not a 20-row fixture.
-   Rows virtualize past ~200 visible (CLAUDE.md §10).
-   Every filter/search state is reflected in the URL (shareable, back-button safe).
-   Bulk action on a partial-failure batch reports exactly which rows failed and why.

**Tests**

-   Unit: filter/query-param serialization.
-   Integration: data-table primitive — sort, filter, paginate, export, bulk action success and partial-failure paths.
-   E2E: search for a known product, filter to low-stock, export, open one item's detail page.

**Commit checkpoint:** `feat(inventory): table, filters, export, bulk actions, detail page`

* * *

## ═══ SPRINT CUT LINE — Stages 0–2 above are the realistic 2–3 week scope ═══

Everything below is the full roadmap. Build it if you've chosen ship-long; otherwise leave it as the documented plan and say so in the README.

* * *

## Stage 3 — Products

**Goals:** full product lifecycle management.

**Tasks**

-   \[ \] Product list (reuses `data-table` primitive, same pattern as Inventory)
-   \[ \] Product CRUD — create/edit forms via the shared `forms` primitive with zod validation matching StockPilot Core's constraints
-   \[ \] Categories — assign/manage, filter by category
-   \[ \] Brands — assign/manage, filter by brand
-   \[ \] Images — upload, preview, reorder, delete (confirm the backend's storage contract before building — don't assume direct blob upload without checking `contracts/`)
-   \[ \] Pricing — cost price, sale price, margin display (margin computed client-side from two real fields is fine; label it as computed if the UI shows a provenance-style badge anywhere)
-   \[ \] Product history — audit trail of changes to this product (price changes, stock adjustments) if the backend exposes it; flag as a contract gap if not

**Acceptance criteria**

-   Create → appears immediately in the list (via query invalidation, not a full reload).
-   Edit form pre-fills correctly from real data; validation errors map to the correct field.
-   Delete is confirmed, and blocked with a specific message if the product has dependent records (open PO lines, existing orders).

**Tests**

-   Unit: pricing/margin formatting, validation schema.
-   Integration: form primitive (create, edit, validation error display).
-   E2E: create a product end to end, edit its price, delete it.

**Commit checkpoint:** `feat(products): CRUD, categories, brands, images, pricing, history`

* * *

## Stage 4 — Suppliers

**Goals:** supplier relationship management feeding into Purchase Orders.

**Tasks**

-   \[ \] Supplier list + CRUD (same shared primitives)
-   \[ \] Contact management — multiple contacts per supplier
-   \[ \] Purchase history — POs placed with this supplier, linked
-   \[ \] Supplier performance — on-time delivery rate, defect/return rate if the backend computes it; if not in `contracts/`, this is a contract gap to flag, not a client-side estimate to fabricate

**Acceptance criteria**

-   Supplier detail page correctly aggregates linked POs without a second ad hoc fetch pattern (reuse the PO list component filtered by supplier).
-   Performance metrics, if shown, are explicitly labeled with their source and time window.

**Tests**

-   Integration: supplier CRUD, contact sub-form.
-   E2E: create supplier, add a contact, verify it's linked from a PO created in Stage 5's tests.

**Commit checkpoint:** `feat(suppliers): CRUD, contacts, purchase history, performance`

* * *

## Stage 5 — Purchase Orders

**Goals:** the most stateful workflow in the app — a real status machine, not a free-text status field.

**Tasks**

-   \[ \] Create PO — select supplier, add line items (product + quantity + cost), computed totals
-   \[ \] Status workflow per the PO lifecycle defined in `docs/PRODUCT-SPEC.md` §10 and §12 (exact states per `contracts/` — don't invent a workflow the backend doesn't enforce)
-   \[ \] Receive stock — full and partial receipt flows, updating inventory levels through the real endpoint, never a client-side inventory mutation
-   \[ \] Partial receipts — line-level received-quantity tracking, remaining balance visible
-   \[ \] PO detail page — line items, status history, linked supplier, linked receipts

**Acceptance criteria**

-   Every status transition is only available when valid for the current state (no "Receive" action visible on a Draft PO).
-   Partial receipt correctly leaves the PO in "Partially Received" and shows remaining quantity per line.
-   Inventory levels reflect a receipt immediately after confirmation (query invalidation across Inventory + Dashboard KPI, not just the PO view).

**Tests**

-   Unit: status-transition validity logic.
-   Integration: PO creation, partial receipt math, status transitions.
-   E2E: create PO → submit → approve → partially receive → fully receive → verify inventory updated and dashboard KPI reflects it.

**Commit checkpoint:** `feat(purchase-orders): create, status workflow, partial receiving`

* * *

## Stage 6 — Sales

**Goals:** revenue side of the business, feeding the Dashboard and Analytics.

**Tasks**

-   \[ \] Sales dashboard (page-level, distinct from the global Dashboard — deeper revenue breakdowns, by product/category/period)
-   \[ \] Orders list + detail
-   \[ \] Customers — list, detail, order history per customer
-   \[ \] Revenue reporting views (period comparison, top products)

**Acceptance criteria**

-   Sales dashboard figures reconcile with the global Dashboard's revenue KPI for the same period (same source endpoint, not two divergent calculations).
-   Customer detail correctly lists their order history via the shared list component, filtered.

**Tests**

-   Integration: order list, customer detail aggregation.
-   E2E: view an order, navigate to its customer, verify order history includes it.

**Commit checkpoint:** `feat(sales): dashboard, orders, customers, revenue reporting`

* * *

## Stage 7 — Forecasting

**Goals:** surface StockPilot Core's forecasting output with honest uncertainty representation — this is the one place ERP scope and the copilot's provenance discipline directly overlap, so it's worth extra care.

**Tasks**

-   \[ \] Forecast charts — demand prediction over time, per product or category
-   \[ \] Confidence intervals rendered as gradient/fan bands per `docs/DESIGN-SPEC.md`'s chart rules — never a flat band implying false certainty (same research basis as the copilot's forecast view; reuse that chart component rather than rebuilding it)
-   \[ \] Explicit interval labeling ("80% prediction interval") on every band
-   \[ \] Forecast vs. actual overlay where historical data allows it

**Acceptance criteria**

-   Forecast charts use the same band-rendering component as RetailOps AI's copilot forecast view — not a second, divergent implementation.
-   Every band is labeled with its interval type; no unlabeled shaded region.

**Tests**

-   Unit: interval-band data transform.
-   Integration: chart renders correctly across data availability (full history, sparse history, no history yet for a new product).

**Commit checkpoint:** `feat(forecasts): demand charts with labeled prediction intervals`

* * *

## Stage 8 — Analytics

**Goals:** executive-level rollups — the page most likely to be screenshotted in a portfolio review, so it needs to be genuinely well-composed, not just comprehensive.

**Tasks**

-   \[ \] Executive dashboard — the highest-altitude view, distinct from Stage 1's operational Dashboard
-   \[ \] Inventory turnover analysis
-   \[ \] ABC analysis (product value/velocity classification)
-   \[ \] Dead stock report
-   \[ \] Supplier analytics (aggregated performance across suppliers, distinct from Stage 4's per-supplier view)

**Acceptance criteria**

-   Every analytical figure traces to a specific StockPilot Core endpoint or a documented, disclosed client-side aggregation — no unlabeled derived math presented as if it were raw data.
-   Page is scannable in under 30 seconds — hierarchy matters as much as completeness here.

**Tests**

-   Unit: ABC classification logic, turnover calculation (if computed client-side and disclosed as such — otherwise this is backend-tested, not frontend).
-   Integration: each analytics panel across populated/empty/error states.

**Commit checkpoint:** `feat(analytics): executive dashboard, turnover, ABC, dead stock, supplier analytics`

* * *

## Stage 9 — Settings

**Goals:** the administrative backbone — users, roles, permissions, audit, system config. Build against the role set in `docs/PRODUCT-SPEC.md` §6 and the authorization mechanics in `docs/ARCHITECTURE.md` § Authorization (RBAC) — confirm the provisional role set against StockPilot Core's actual auth model before this stage starts, not after building the permission matrix UI.

**Tasks**

-   \[ \] User management — list, invite, deactivate
-   \[ \] Role management — define roles, assign permissions per the RBAC model in `lib/rbac/`
-   \[ \] Permissions — a real permission matrix UI, not a free-text role field
-   \[ \] Audit logs — list of system actions (who did what, when), filterable by user/resource/date
-   \[ \] API keys — generate, revoke, scope
-   \[ \] System settings — whatever tenant-level config StockPilot Core exposes (currency, timezone, notification preferences) — don't invent settings the backend doesn't persist
-   \[ \] Profile page — the current user's own settings, distinct from admin user management

**Acceptance criteria**

-   Role/permission changes take effect on next action check (not requiring a full re-login) where the backend token model supports it — otherwise this is a documented limitation, not a silent gap.
-   Audit log is genuinely useful for finding "who changed this PO's status on this date" — verify with a real query during testing, not just that the list renders.
-   A user without admin permission cannot reach `/settings/users` even by direct URL — server-side route guard, not just a hidden nav link.

**Tests**

-   Unit: permission matrix logic.
-   Integration: RBAC gating — an allowed role succeeds, a denied role is blocked with a specific message, both at the UI and route-guard level.
-   E2E: create a role with limited permissions, assign to a test user, verify the gated pages are inaccessible.

**Commit checkpoint:** `feat(settings): users, roles, permissions, audit logs, api keys, profile`

* * *

## Stage 10 — RetailOps AI integration

**Goals:** the actual product differentiator — bring the copilot into every page as context-aware assistance, not a bolted-on chat widget. Technical contract (context-passing shape, streaming, component-reuse decision) is in `docs/ARCHITECTURE.md` § AI Integration Architecture; behavioral rules (wording, scope-by-role, what the assistant can and can't do) are in `docs/PRODUCT-SPEC.md` §14. The component-reuse ADR referenced there (shared package vs. tracked duplication) should be decided before this stage's tasks start, not discovered mid-implementation.

**Tasks**

-   \[ \] AI sidebar — persistent, collapsible, mounted in the Stage 0 shell
-   \[ \] "Ask AI" entry point from every page, pre-seeding the sidebar with page context (e.g. opening it from a Product detail page includes that product's ID in the initial context so the copilot doesn't have to be told)
-   \[ \] Context-aware queries — the sidebar knows what page/resource the user is looking at and passes that as context to RetailOps AI's backend, per its query contract
-   \[ \] "Explain this metric" affordance on Dashboard/Analytics figures — opens the sidebar with a query pre-filled to explain that specific number, using the same citation-chip/provenance-drawer pattern the copilot already implements (reuse the components, don't rebuild them in this repo)
-   \[ \] Generate recommendations — surfaces RetailOps AI recommendations relevant to the current resource inline (e.g. a reorder recommendation shown on the relevant Inventory Details page), with the same Accept/Reject/Snooze wording rules as the copilot (recommendations are never phrased as actions taken)

**Acceptance criteria**

-   Opening the AI sidebar from three different pages (Dashboard, a Product detail, Purchase Orders) demonstrably passes different context each time — verify via network inspection, not just visually.
-   The sidebar's citation chips and provenance drawer are visually and behaviorally identical to the copilot's own — same component library or a genuinely shared package, not a reimplementation that could drift.
-   No recommendation surfaced in this app implies an action was taken automatically.

**Tests**

-   Integration: sidebar context-passing per entry point.
-   E2E: open AI sidebar from a Product page, ask a question, verify a citation chip opens the correct provenance drawer.

**Commit checkpoint:** `feat(ai-integration): context-aware sidebar, ask-ai entry points, inline recommendations`

* * *

## Stage 11 — Testing

**Goals:** close any gaps left by per-stage testing; this stage is a hardening pass, not the first time tests are written.

**Tasks**

-   \[ \] Unit test coverage review across `lib/`, `hooks/`, `lib/validation/`
-   \[ \] Integration coverage review across shared primitives and every resource's CRUD/list flow
-   \[ \] Playwright E2E suite covering one full happy path per resource plus the cross-cutting flows (auth, RBAC denial, AI sidebar context)
-   \[ \] Accessibility — automated axe-core in CI on every route; manual screen-reader pass on Inventory, Purchase Orders, and Settings (the three highest-complexity surfaces)
-   \[ \] Performance — Lighthouse CI on Dashboard and Inventory against the budgets in `CLAUDE.md` §10; fix regressions before proceeding

**Acceptance criteria**

-   CI runs unit + integration + E2E + accessibility + performance checks on every PR, all green on main.
-   No known accessibility violation above "serious" severity left unaddressed (documented exceptions, if any, are explicit and justified).

**Tests:** this stage's output _is_ the test suite — see tasks above.

**Commit checkpoint:** `test: full coverage pass — unit, integration, e2e, a11y, performance`

* * *

## Stage 12 — Production deployment

**Goals:** a live, monitored, reviewable production instance.

**Tasks**

-   \[ \] Vercel project configured, environment variables set, connected to the real StockPilot Core deployment (or a stable staging instance)
-   \[ \] Preview deployments verified working on PRs
-   \[ \] Error tracking (Sentry or equivalent) confirmed capturing real errors in the deployed environment, not just locally
-   \[ \] Uptime/monitoring on the deployed frontend and its dependency on StockPilot Core's availability
-   \[ \] CI/CD: main branch auto-deploys after all checks pass; no manual deploy step for routine changes
-   \[ \] Full checklist in `CLAUDE.md` §16 walked and confirmed
-   \[ \] README finalized: what this is, architecture diagram (four deployables), local setup, live URL, screenshots, and — if ship-thin was chosen — an explicit, honest note on which stages are fully built vs. documented roadmap

**Acceptance criteria**

-   Cold load of the deployed URL, full click-through of every built page, zero console errors.
-   A deliberately triggered error appears in the error tracker within minutes.
-   Someone with no prior context can read the README and understand the four-deployable architecture and what's live vs. planned.

**Tests:** deployment smoke test (E2E suite run against the deployed URL, not just localhost).

**Commit checkpoint:** `chore: production deployment, monitoring, final README`

* * *

## Notes for the working session

-   Don't start a stage's checkpoint task from a blank prompt — reference the specific unchecked box.
-   Contract or design-token gaps get flagged, not silently resolved by invention — see `CLAUDE.md` §18.
-   Update checkboxes as you go. A session that finishes a task without checking it off leaves the next session guessing what's real.
-   If you're building ship-thin, stages below the cut line stay unchecked and the README says so explicitly — an honestly-scoped 3-stage app is a stronger portfolio piece than a 13-stage app with silently unfinished corners.