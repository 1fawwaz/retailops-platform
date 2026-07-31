# BUILD.md — StockPilot ERP Implementation Roadmap (Backend + Frontend)

This is the complete roadmap for StockPilot — _in what order_ the backend (StockPilot Core) and frontend (StockPilot Frontend) get built. For _what_ to build, see `docs/PRODUCT-SPEC.md`; for _how the system is designed_, see `docs/ARCHITECTURE.md` (§24 in particular, for the backend module list this file mirrors); for engineering rules and quality gates, see `CLAUDE.md` — read that first. This file's job is sequencing and per-module checkpoints, not restating requirements or design decisions already covered in those docs.

## Timeline — stated honestly, not as a sprint

**This is a full ERP: a real multi-module backend (Purchase Orders, Sales, Customers, a real Users/Roles/Permissions system, Notifications, Audit Logs) plus the frontend consuming it, built to production quality with real tests at every step.** That is not a 2–3 week project. It is realistically many weeks of focused work even before accounting for the AI integration (Stage: AI Sidebar) and hardening/deployment passes. There is no "ship-thin" cut line in this version of the roadmap — every module below is built for real, in order, with its own tests and its own commit, and the honest way to run this is: work through it steadily, module by module, and report status truthfully rather than declaring the whole thing "done" before it is. If time runs out at any point, the correct move is to stop with whatever prefix of modules is genuinely complete and say exactly that — not to mark a partially-built module `[x]`.

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done, verified (tests pass, lint/typecheck/build clean, committed)

* * *

## Status summary (updated as modules complete)

| Track | Module | Status |
| --- | --- | --- |
| Frontend | Stage 0 — Bootstrap | `[x]` |
| Frontend | Stage 1 — Dashboard | `[x]` (against the CURRENT backend surface — see its own note below on what's still missing) |
| Frontend | Stage 2 — Inventory | `[x]` (ditto) |
| Backend | Module 1 — Authentication | `[~]` login/register live; logout/refresh/me/password-reset extension in progress |
| Backend | Modules 2–10 | `[ ]` |
| Frontend | Products / Suppliers / Purchase Orders / Customers / Sales / Forecast / Analytics / Reports / Notifications / Audit Logs / Settings / AI Sidebar | `[ ]` |

* * *

## Part A — Backend module order (StockPilot Core)

Each module: check what already exists (`docs/stockpilot-gaps.md`, `contracts/stockpilot-api/`) before building — extend and harden real gaps, never rebuild functionality that already works. Every module follows the existing codebase's own established conventions (SQLAlchemy 2.x, Pydantic v2, Alembic, ruff + mypy --strict, pytest, `_provenance`/`_derivation_ref` labeling on derived fields) — see `docs/ARCHITECTURE.md` §24.

### Backend Module 1 — Authentication (extend, don't rebuild)

**Status:** `/auth/login` and `/auth/register` are live and correct (bearer JWT, `docs/adr/001-session-management.md`). This module adds what's genuinely missing.

**Tasks**

- [ ] `POST /auth/logout` — revokes the caller's refresh token (see `docs/ARCHITECTURE.md` §6 for the exact contract)
- [ ] `POST /auth/refresh` — exchanges a valid refresh token for a new access token
- [ ] `refresh_tokens` table + Alembic migration (user_id, token hash, expires_at, revoked_at)
- [ ] `GET /me` — returns the authenticated user + resolved role names + resolved permission set (the same shape § Authorization defines; both a future Profile page and the frontend's RBAC layer consume this one endpoint)
- [ ] `POST /auth/password-reset/request` + `POST /auth/password-reset/confirm` — see `docs/ARCHITECTURE.md` §6's explicit flag on the email-delivery dependency this needs; resolve that dependency (or explicitly scope reset to admin-initiated for now) before marking this task done, not after
- [ ] `contracts/stockpilot-api/` regenerated to reflect every new endpoint

**Acceptance criteria**

- A logged-in user can call `/me` and get back roles/permissions matching what they were actually assigned.
- A revoked refresh token cannot be used to obtain a new access token (401, not a silent success).
- Password reset either genuinely delivers a usable reset link, or the module's own README/PR states plainly that it's admin-initiated-only for now — no half-real email flow shipped silently.

**Tests:** unit (token generation/validation, refresh-token revocation logic), integration (full login → refresh → logout cycle; password-reset request/confirm cycle), contract (OpenAPI export matches deployed routes).

**Commit checkpoint:** `feat(auth): logout, refresh tokens, /me, password reset`

* * *

### Backend Module 2 — Products (extend)

**Status:** list/get/create/update/delete are live. Missing: categories as a real resource, brands, images, sale price, product history.

**Tasks**

- [ ] `categories` table (id, name) + `GET/POST /categories` — replaces the free-floating `category_id` FK with something actually manageable
- [ ] `brands` table + brand FK on products + `GET/POST /brands`
- [ ] Image storage decision (object storage provider — a new infrastructure dependency, flag and confirm before implementing, don't assume one) + `product_images` table + upload/list/delete endpoints
- [ ] `sale_price` field on products (distinct from the existing `unit_cost`) — confirm sourcing (manually set vs. derived from `sales_transactions.unit_price`, `docs/stockpilot-gaps.md` #2) before adding the column
- [ ] `product_history` — an append-only audit trail of price/reorder-point/etc. changes to a product, `GET /products/{sku}/history`

**Acceptance criteria:** creating/editing a product with a category, brand, image, and sale price round-trips correctly; history shows every change with who/when.

**Tests:** unit (validation), integration (CRUD + history recording on every mutating call), contract.

**Commit checkpoint:** `feat(products): categories, brands, images, sale price, history`

* * *

### Backend Module 3 — Suppliers (extend)

**Status:** list/get/create/update/delete are live. Missing: contacts, purchase-history linkage (depends on Module 5), performance metrics.

**Tasks**

- [ ] `supplier_contacts` table (multiple contacts per supplier) + CRUD endpoints
- [ ] Supplier performance metrics — on-time delivery rate, defect/return rate; defer the exact computation until Module 5 (Purchase Orders) exists to source it from, don't fabricate an interim number
- [ ] `GET /suppliers/{id}/purchase-orders` once Module 5 exists

**Acceptance criteria:** a supplier's contacts and (once Module 5 ships) linked POs are real, queryable data.

**Tests:** unit, integration (contact CRUD), contract.

**Commit checkpoint:** `feat(suppliers): contacts, performance metrics, PO linkage`

* * *

### Backend Module 4 — Inventory (extend: warehouses, multi-location, transfers, adjustments, ledger)

**Status:** single-location stock/low-stock/dead-stock/slow-movers/valuation queries are live. The underlying `stock_levels`/`stock_movements` tables already carry full history (`docs/stockpilot-gaps.md` #3) — this module exposes what already exists in the data plus adds real multi-location support.

**Tasks**

- [ ] `warehouses` table + location field on stock queries
- [ ] Multi-location stock levels — every inventory endpoint gains a location dimension without breaking the existing single-location callers (additive, not breaking)
- [ ] `POST /inventory/transfers` — move stock between locations, real ledger entries, not a silent quantity edit
- [ ] `POST /inventory/adjustments` — manual stock correction with a required reason, logged
- [ ] `GET /inventory/{sku}/ledger` — the real movement history already in `stock_movements`, finally queryable directly instead of only replayed internally

**Acceptance criteria:** a transfer between two locations is reflected correctly at both ends and in the ledger; an adjustment requires and records a reason.

**Tests:** unit (ledger math), integration (transfer/adjustment flows, multi-location queries), contract.

**Commit checkpoint:** `feat(inventory): warehouses, transfers, adjustments, ledger API`

* * *

### Backend Module 5 — Purchase Orders (new)

**Tasks**

- [ ] `purchase_orders` + `purchase_order_lines` tables, status enum matching `docs/PRODUCT-SPEC.md` §10/§12's lifecycle exactly (Draft → Submitted → Approved → Partially Received → Received → Closed)
- [ ] CRUD + status-transition endpoints, each transition validated server-side (no skipping states, no editing a Submitted+ PO's lines)
- [ ] Receive endpoint (full/partial), updates `stock_levels`/`stock_movements` through the same real inventory-mutation path Module 4 established — never a second, divergent stock-update code path
- [ ] Over-receipt handling — flagged distinctly per `docs/PRODUCT-SPEC.md` §12, not silently accepted

**Acceptance criteria:** every transition in `docs/PRODUCT-SPEC.md` §10 is enforced server-side; a partial receive leaves the PO in the correct state and inventory reflects it immediately.

**Tests:** unit (status-transition validity), integration (full create→submit→approve→partially-receive→receive cycle, verifying inventory + ledger), contract.

**Commit checkpoint:** `feat(purchase-orders): CRUD, status workflow, receiving`

* * *

### Backend Module 6 — Customers (new)

**Tasks**

- [ ] `customers` table + CRUD endpoints
- [ ] `GET /customers/{id}/orders` (depends on Module 7)

**Acceptance criteria:** a customer's order history is real, queryable data once Module 7 exists.

**Tests:** unit, integration, contract.

**Commit checkpoint:** `feat(customers): CRUD`

* * *

### Backend Module 7 — Sales (new: orders, invoices, payments)

**Tasks**

- [ ] `sales_orders` + `sales_order_lines` tables, linked to `customers`
- [ ] `invoices` table linked to orders
- [ ] `payments` table linked to invoices, with a status (pending/paid/partial/failed) — no real payment-provider integration assumed unless explicitly decided; if none is in scope, payments are recorded, not processed (state a real payment gateway is out of scope rather than half-implementing one)
- [ ] Revenue reporting views reconciling with existing `/analytics/revenue` (same source data, not a second divergent calculation)

**Acceptance criteria:** an order → invoice → payment chain is queryable end to end; Sales' own revenue figures match `/analytics/revenue` for the same period.

**Tests:** unit, integration (order→invoice→payment), contract.

**Commit checkpoint:** `feat(sales): orders, invoices, payments`

* * *

### Backend Module 8 — Analytics (extend)

**Status:** revenue/profit/turnover/ABC/top-bottom-products/period-comparison are live.

**Tasks**

- [ ] Supplier-aggregated analytics (cross-supplier performance rollup, distinct from Module 3's per-supplier view)
- [ ] PO-derived KPIs (open PO count, average time-to-receive) now that Module 5 exists

**Acceptance criteria:** every new analytics figure traces to real data, provenance-labeled per `docs/PRODUCT-SPEC.md` §13.

**Tests:** unit (aggregation logic), integration, contract.

**Commit checkpoint:** `feat(analytics): supplier rollups, PO-derived KPIs`

* * *

### Backend Module 9 — Forecasting

**Status:** demand forecast and forecast-accuracy are live (`POST /forecast/demand`, `GET /forecast/accuracy`) — a single predicted-daily-demand point with a confidence interval, not a per-day time series. Confirm with the actual product need (`BUILD.md` Frontend — Forecast module, `docs/PRODUCT-SPEC.md` §24) whether a real per-day series endpoint is needed before building one; don't add API surface speculatively.

**Tasks**

- [ ] Reorder-point prediction endpoint, if the frontend forecast/reorder UX needs one beyond what `reorder_point`/`safety_stock` on products already provide
- [ ] Re-verify forecast accuracy reporting is genuinely useful (not just present) once real usage exists

**Commit checkpoint:** `feat(forecasting): reorder prediction` (only if genuinely needed — see task note)

* * *

### Backend Module 10 — Administration (Users, Roles, Permissions, Audit Logs, Notifications, Settings)

**Real backend functionality, not an invented layer on top of an unsupported backend** — see `docs/ARCHITECTURE.md` §7 for the full decided data model (`roles`/`user_roles`, many-to-many) before starting this module.

**Tasks**

- [ ] `roles` + `user_roles` tables + migration, seeded with the six default roles from `docs/PRODUCT-SPEC.md` §6 / `lib/rbac/permissions.ts`
- [ ] `GET/POST /roles`, `PUT /roles/{id}` — role + permission-set management
- [ ] `GET /users`, `POST /users/{id}/roles` (assign/revoke) — user/role management, building on Module 1's `/auth/register` and `/me`
- [ ] Server-side permission enforcement — a dependency every mutating endpoint across every module above uses to check the caller's resolved permission set; this is the task that makes the whole RBAC model real, not just data structures nothing checks
- [ ] `audit_logs` table + middleware/hook recording every mutating request (who, what, when, before/after where feasible) across every module
- [ ] `notifications` table + triggers matching `docs/PRODUCT-SPEC.md` §16 (low-stock crossing threshold, PO awaiting approval, forecast revision, new AI recommendation) + `GET/PATCH /notifications`
- [ ] `settings` table (tenant-level: currency, timezone, notification defaults) + `GET/PUT /settings`
- [ ] API key management (`api_keys` table, generate/revoke/scope) if genuinely needed for machine-to-machine access beyond the JWT model already in place — confirm the actual use case before building rather than adding it speculatively

**Acceptance criteria:** a user without a permission genuinely cannot perform the gated action via direct API call (not just hidden in the UI); the audit log answers "who changed this PO's status on this date" from a real query; notifications fire on the real triggers, not a hardcoded demo list.

**Tests:** unit (permission-resolution logic), integration (RBAC enforcement — allowed role succeeds, denied role gets a real 403, for every module's mutating endpoints), contract.

**Commit checkpoint:** `feat(admin): roles, permissions enforcement, audit logs, notifications, settings`

* * *

## Part B — Frontend module order (StockPilot Frontend)

Build each module's frontend once its backend module exists and is stable — not before, and not by inventing a shape the backend doesn't have (`CLAUDE.md` §18). Dashboard, Inventory, and (once started) the AI Sidebar are frontend-first exceptions already built against the CURRENT backend surface — each is explicitly re-scoped below rather than assumed finished forever, since new backend capability changes what they can honestly show.

### Frontend — Dashboard `[x]` (revisit after Backend Modules 5 and 10)

Built (this session) against the live backend at the time: revenue, inventory value, low-stock count, wired to real endpoints. Open PO count and the activity feed were explicitly NOT built — no backend source existed. **Revisit once Backend Module 5 (Purchase Orders) ships**, to add the Open PO count KPI and a real activity feed, and once Backend Module 10 ships, to add AI-recommendation items to that feed per the original design.

### Frontend — Inventory `[x]` (revisit after Backend Module 4)

Built (this session): search/category/low-stock filtering, server-side pagination, CSV export, Inventory Details (product + live stock + supplier + forecast). Warehouse/location filtering, supplier filtering, and bulk actions were explicitly NOT built — no backend source existed. **Revisit once Backend Module 4 ships** (warehouses, transfers, adjustments) to add location filtering and, if a real bulk-mutation endpoint exists by then, bulk actions.

### Frontend — Products (after Backend Module 2)

List/CRUD, categories, brands, images, pricing, history — one-to-one with Backend Module 2's new endpoints. Reuses `DataTable`/`Form` primitives from Stage 0.

### Frontend — Suppliers (after Backend Module 3)

List/CRUD, contacts, purchase history (once Module 5 exists), performance metrics.

### Frontend — Purchase Orders (after Backend Module 5)

Create PO, status workflow UI (only valid transitions ever shown as available actions), receive (full/partial) flow, PO detail page.

### Frontend — Customers (after Backend Module 6)

List, detail, order history (once Module 7 exists).

### Frontend — Sales (after Backend Module 7)

Sales dashboard, orders list/detail, customers, revenue reporting — reconciled against the global Dashboard's own revenue KPI (same source, not a second calculation).

### Frontend — Forecast (after Backend Module 9)

Forecast display honoring the real shape (`docs/ARCHITECTURE.md` §24's note: a single predicted-daily-demand point today, not a time series) — build the UI against what the endpoint actually returns, not an assumed richer shape; revisit if Module 9 adds a real per-day series.

### Frontend — Analytics (after Backend Module 8)

Executive rollup: turnover, ABC, dead stock, supplier analytics.

### Frontend — Reports (after Backend Module 8, reuses Analytics data)

Standard exportable reports per `docs/PRODUCT-SPEC.md` §15.

### Frontend — Notifications (after Backend Module 10)

Notification center: read/unread, mark-read, click-through to the relevant resource.

### Frontend — Audit Logs (after Backend Module 10)

Filterable (user/resource/date) log view, admin-only.

### Frontend — Settings (after Backend Module 10)

User management, role management (a real permission-matrix editor against the real `roles` data), system settings, profile.

### Frontend — AI Sidebar

Context-aware sidebar, "Ask AI" entry points, "Explain this metric," inline recommendations — per `docs/ARCHITECTURE.md` § AI Integration Architecture and `docs/PRODUCT-SPEC.md` §14. **Scoped to the real authorization model** (`docs/ARCHITECTURE.md` §7): until Backend Module 10 ships, there is no real per-user role/permission data to scope the sidebar against — build it against whatever `is_active`/`is_read_only` genuinely support today, and document the gap rather than inventing role-based sidebar scoping the backend can't yet enforce. See the Gap Report this stage produces.

* * *

## Testing, CI, accessibility, performance — a hardening pass, not deferred entirely

Per-module tests (above) are not optional and are not deferred to a single "Stage 11" at the end the way the earlier frontend-only roadmap had it — every module ships with its own real tests. A final hardening pass still happens before calling the whole system production-ready:

- [ ] Playwright E2E covering one full happy path per resource, both backend and frontend, plus cross-cutting flows (auth, RBAC denial, AI sidebar context)
- [ ] Accessibility — automated axe-core in CI on every route; manual screen-reader pass on Inventory, Purchase Orders, and Settings
- [ ] Performance — Lighthouse CI on Dashboard and Inventory against `CLAUDE.md` §10's budgets
- [ ] Full backend contract test suite passing against a real deployed instance, not just local

## Production deployment

- [ ] Both StockPilot Core (expanded) and StockPilot Frontend deployed, environment variables set, connected end to end
- [ ] Error tracking confirmed capturing real errors in the deployed environment
- [ ] CI/CD: main branch auto-deploys after all checks pass
- [ ] `FINAL_REPORT.md` generated: completed modules, API endpoint list, database schema, frontend pages, remaining work, known limitations — all measured, not asserted (`CLAUDE.md`'s honesty rule applies to this report too)

* * *

## Notes for the working session

- Don't start a module's checkpoint task from a blank prompt — reference the specific unchecked box.
- Contract or design gaps get flagged in `docs/stockpilot-gaps.md`, not silently resolved by invention — see `CLAUDE.md` §18.
- Update checkboxes as you go. A session that finishes a task without checking it off leaves the next session guessing what's real.
- Keep `contracts/stockpilot-api/` (the OpenAPI export) synchronized with the backend at every module, not reconciled at the end — a stale contract doc is worse than none (`docs/ARCHITECTURE.md` §5).
