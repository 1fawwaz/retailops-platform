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
| Backend | Module 1 — Authentication | `[x]` logout, refresh, `GET /me`, password reset (admin-mediated delivery — see note) all live, tested, committed |
| Backend | Module 2 — Products | `[~]` categories, brands, sale price, history all live; images blocked on a storage-provider decision (see note) |
| Backend | Module 3 — Suppliers | `[~]` contacts live; performance metrics deferred to Module 5 (see note) |
| Backend | Module 4 — Inventory | `[x]` warehouses, location-scoped stock, transfers, adjustments, ledger all live, tested, committed |
| Backend | Module 5 — Purchase Orders | `[x]` new `purchase_order_requests` tables (existing synthetic `purchase_orders` untouched), full lifecycle + receiving, tested, committed |
| Backend | Module 6 — Customers | `[x]` CRUD live, tested, committed; order-history endpoint now live (Module 7) |
| Backend | Module 7 — Sales | `[x]` new `sales_orders`/`invoices`/`payments` tables (existing `sales_transactions` untouched, two eras never merged), full lifecycle, tested, committed |
| Backend | Module 8 — Analytics | `[x]` supplier rollup + PO-derived KPIs live; also fixed a latent Module-4 turnover bug (see note), tested, committed |
| Backend | Modules 9–10 | `[ ]` |
| Frontend | Products / Suppliers / Purchase Orders / Customers / Sales / Forecast / Analytics / Reports / Notifications / Audit Logs / Settings / AI Sidebar | `[ ]` |

* * *

## Part A — Backend module order (StockPilot Core)

Each module: check what already exists (`docs/stockpilot-gaps.md`, `contracts/stockpilot-api/`) before building — extend and harden real gaps, never rebuild functionality that already works. Every module follows the existing codebase's own established conventions (SQLAlchemy 2.x, Pydantic v2, Alembic, ruff + mypy --strict, pytest, `_provenance`/`_derivation_ref` labeling on derived fields) — see `docs/ARCHITECTURE.md` §24.

### Backend Module 1 — Authentication (extend, don't rebuild) `[x]`

**Status:** `/auth/login` and `/auth/register` are live and correct (bearer JWT, `docs/adr/001-session-management.md`). This module's extensions are now live too.

**Tasks**

- [x] `POST /auth/logout` — revokes the caller's refresh token; idempotent (204 always)
- [x] `POST /auth/refresh` — exchanges a valid refresh token for a new access token (no rotation in this cut, flagged as a fast-follow per `docs/ARCHITECTURE.md` §6)
- [x] `refresh_tokens` table + Alembic migration (`c1a2b3d4e5f6`) — user_id, token_hash (sha256, unique), expires_at, revoked_at; `/auth/login` now returns `{access_token, refresh_token, token_type}`
- [x] `GET /me` — top-level route (not `/auth/me`), returns the authenticated user's profile. **Scoped down from the original task description:** it does NOT yet return a resolved permission set — there is no roles/permissions data to resolve until Backend Module 10 ships. Extending this same endpoint's response shape with roles/permissions is now an explicit Module 10 task, not redone here.
- [x] `POST /auth/password-reset/request` + `POST /auth/password-reset/confirm` — `password_reset_tokens` table (same migration), single-use, expiring, never returned in the API response. **Email-delivery dependency resolved by explicit scope-down** (the option `docs/ARCHITECTURE.md` §6 itself authorized): no transactional email provider is integrated in this pass. The endpoint is real end-to-end (request generates a real single-use token server-side, confirm consumes it and revokes every other session) but delivery to the end user is admin/support-mediated for now, not automatic email. Revisit if/when a transactional email provider is chosen — a genuine new-infrastructure decision, not defaulted here.
- [x] `contracts/stockpilot-api/` regenerated (`scripts/export_contracts.py`) to reflect every new endpoint

**Acceptance criteria**

- ~~A logged-in user can call `/me` and get back roles/permissions matching what they were actually assigned~~ — superseded: `/me` returns profile only until Module 10; re-verify this criterion when Module 10 extends it.
- A revoked refresh token cannot be used to obtain a new access token (401, not a silent success) — verified by test.
- Password reset does not ship a half-real email flow: the flow is real, but delivery is explicitly admin-mediated, stated plainly here rather than assumed automatic.

**Tests:** `tests/test_auth.py` — 16 tests covering login issuing a refresh token, `/me` (authed and unauthenticated), refresh (valid/unknown token), logout (revokes, idempotent on unknown token), password-reset request (202 for both real and unknown accounts, never distinguishing), password-reset confirm (changes password, revokes all other refresh tokens, rejects invalid/expired/already-used tokens). Full suite (135 tests) + contract tests pass; ruff, ruff format, and mypy --strict clean.

**Commit checkpoint:** `feat(auth): logout, refresh tokens, /me, password reset`

**Known limitation carried forward, not silently dropped:** password-reset tokens are generated and stored but have no automated delivery channel yet — see the task note above and `docs/ARCHITECTURE.md` §6.

* * *

### Backend Module 2 — Products (extend) `[~]`

**Status:** list/get/create/update/delete are live. Categories, brands, sale price, and product history are now live too. Images remain genuinely blocked — see below.

**Tasks**

- [x] `categories` — the `Category` model/table already existed (used by `Product.category_id`) but had no CRUD API; added `GET/POST /categories`.
- [x] `brands` table + `Product.brand_id` FK + `GET/POST /brands`.
- [ ] **Image storage — deliberately not built, not silently skipped.** Requires choosing and paying for a new external object-storage provider (S3/R2/Cloudinary/etc.) plus a new secret — a real infrastructure/cost decision neither `docs/ARCHITECTURE.md` nor `docs/PRODUCT-SPEC.md` makes, unlike the password-reset email case which had a pre-authorized fallback. Not defaulted here. Revisit once a provider is chosen.
- [x] `sale_price` field on products — sourced as decided: backfilled from each SKU's average observed `sales_transactions.unit_price` (per `docs/stockpilot-gaps.md` #2's own suggested fix), nullable, user-editable going forward via `PUT /products/{sku}` exactly like `unit_cost` already is. Products with no sales history keep `sale_price` NULL rather than a fabricated default.
- [x] `product_history` — append-only, one row per changed field per update, records `changed_by_user_id`; `GET /products/{sku}/history`. No-op updates (new value equals current value) do not create a spurious entry.

**Acceptance criteria:** creating/editing a product with a category, brand, and sale price round-trips correctly; history shows every real change with who changed it — verified by test. Image round-trip is out of scope until the storage-provider decision above is made.

**Tests:** `tests/test_categories.py`, `tests/test_brands.py`, plus `tests/test_products.py` additions (brand/sale_price round-trip, history recording, no-op-update produces no history entry, RBAC denial for read-only users on category/brand creation). Full suite (144 tests) + contract tests pass; ruff, ruff format, mypy --strict clean.

**Commit checkpoint:** `feat(products): categories, brands, sale price, history`

**Known limitation carried forward, not silently dropped:** product images are not implemented — see the task note above.

* * *

### Backend Module 3 — Suppliers (extend) `[~]`

**Status:** list/get/create/update/delete are live. Contacts are now live too.

**Tasks**

- [x] `supplier_contacts` table (multiple contacts per supplier) + full CRUD (`GET/POST /suppliers/{id}/contacts`, `PUT/DELETE /suppliers/{id}/contacts/{contact_id}`); a contact scoped to the wrong supplier ID returns 404, not another supplier's data.
- [ ] Supplier performance metrics — on-time delivery rate, defect/return rate. **Still deferred, not fabricated:** no real PO lifecycle data exists yet (Module 5 isn't built, and the existing `purchase_orders` table is synthetic stock-ledger-replay data, not real receiving history — `docs/stockpilot-gaps.md` #6). Computing a metric now would mean estimating or defaulting a number with no real basis. Revisit once Module 5 ships.
- [ ] `GET /suppliers/{id}/purchase-orders` once Module 5 exists

**Acceptance criteria:** a supplier's contacts are real, queryable, and correctly scoped — verified by test. Performance metrics and PO linkage remain out of scope until Module 5.

**Tests:** `tests/test_suppliers.py` additions — contact CRUD, cross-supplier contact isolation (404 not data leakage), contacts-for-nonexistent-supplier is 404. Full suite (148 tests) + contract tests pass; ruff, ruff format, mypy --strict clean.

**Commit checkpoint:** `feat(suppliers): contacts`

**Known limitation carried forward, not silently dropped:** performance metrics and PO linkage — see the task note above.

* * *

### Backend Module 4 — Inventory (extend: warehouses, multi-location, transfers, adjustments, ledger) `[x]`

**Status:** single-location stock/low-stock/dead-stock/slow-movers/valuation queries were live; all now genuinely location-aware underneath, plus real transfers/adjustments/ledger.

**Tasks**

- [x] `warehouses` table, seeded with one `Main Warehouse` row that every pre-existing `stock_levels`/`stock_movements` row is backfilled to via the migration — an explicit label for the one real location the historical data already represented, not a fabricated split.
- [x] `stock_levels` and `stock_movements` both gained a required `warehouse_id`. The "latest quantity per SKU" query (used by `/inventory/stock`, `/low-stock`, `/dead-stock`, `/slow-movers`, `/valuation`) now sums each warehouse's own latest row per SKU rather than assuming one global row — with today's single seeded warehouse this is numerically identical to the old behavior (verified: all pre-existing tests pass unchanged), but it will stay correct once a second warehouse genuinely has stock, instead of silently under-counting. **Deferred, not fabricated:** per-warehouse *filtering* on these five read endpoints (e.g. `?warehouse_id=`) isn't added yet — not useful until real multi-warehouse data exists beyond transfers/adjustments made through the new endpoints below; these endpoints already report cross-warehouse totals correctly.
- [x] `POST /inventory/transfers` — moves stock between two warehouses for a SKU; rejects a same-warehouse transfer (400) and a transfer that would drive the source below zero (400); writes two real `stock_movements` rows (`movement_type='transfer'`), not a silent quantity edit.
- [x] `POST /inventory/adjustments` — manual correction with a required `reason`, rejects an adjustment that would drive stock below zero (400); writes one real `stock_movements` row (`movement_type='adjustment'`).
- [x] `GET /inventory/{sku}/ledger` — the real, un-capped movement history already in `stock_movements`, across every warehouse, finally queryable directly (distinct from `ProductDetail.movement_history`, which stays capped at 90 days for the product page).
- [x] `GET/POST /warehouses` — needed so a transfer has somewhere to move stock to.

**Acceptance criteria:** a transfer between two warehouses is reflected correctly at both ends and in the ledger — verified by test that the cross-warehouse total is unchanged while the per-warehouse ledger entries show the split; an adjustment requires and records a reason; both reject a resulting negative quantity; pre-existing single-warehouse behavior is unchanged (regression-verified, not just asserted).

**Tests:** `tests/test_warehouses.py` (new), plus `tests/test_inventory.py` additions — adjustment changes stock and records a ledger entry, adjustment below zero rejected, transfer moves stock and preserves the cross-warehouse total, transfer with insufficient stock rejected, same-warehouse transfer rejected, unknown SKU/warehouse is 404, read-only user denied on both mutating endpoints, ledger for unknown SKU is 404. Full suite (159 tests) + contract tests pass; ruff, ruff format, mypy --strict clean.

**Commit checkpoint:** `feat(inventory): warehouses, transfers, adjustments, ledger API`

**Known limitation carried forward, not silently dropped:** per-warehouse filtering on the five existing read endpoints — see the task note above.

* * *

### Backend Module 5 — Purchase Orders (new) `[x]`

**Naming decision (user-confirmed):** the pre-existing `purchase_orders` table is synthetic stock-ledger-replay data with no real lifecycle (`docs/stockpilot-gaps.md` #6) and is left completely untouched. The real, live workflow lives in new tables named `purchase_order_requests` / `purchase_order_request_lines` instead of colliding with it.

**Tasks**

- [x] `purchase_order_requests` + `purchase_order_request_lines` tables, status enum matching `docs/PRODUCT-SPEC.md` §10/§12's lifecycle exactly: `draft → submitted → approved → partially_received → received → closed`, plus `cancelled` (only reachable from `draft`/`submitted`, per §12's explicit cancellation-boundary rule).
- [x] CRUD + status-transition endpoints (`POST /purchase-orders`, `GET /purchase-orders`, `GET/PUT /purchase-orders/{id}`, `POST /purchase-orders/{id}/{submit,approve,cancel,close,receive}`), each transition validated server-side — editing (`PUT`) is rejected once a PO leaves `draft`, matching §12's "cannot be edited once Submitted" rule exactly.
- [x] Receive endpoint (full/partial): updates `stock_levels`/`stock_movements` through the exact same `apply_stock_delta` path Module 4 established for transfers/adjustments — no second, divergent stock-update code path. Writes a real `stock_movements` row per receive (`movement_type='purchase_order'`). PO status is recomputed from line totals after every receive (`partially_received` vs `received`), not tracked as a separate mutable flag that could drift from the lines.
- [x] Over-receipt handling: a receive that would push a line's total received above its ordered quantity is rejected (400) unless `over_receipt_confirmed: true` is explicitly passed — flagged distinctly per `docs/PRODUCT-SPEC.md` §12, never silently accepted.
- [x] Enforced two `docs/PRODUCT-SPEC.md` §12 business rules that only became real once live POs existed: a Supplier cannot be deleted while it has an open PO referencing it (409), and a Product cannot be deleted while it has an open PO line (409). `docs/PRODUCT-SPEC.md` §12's full product-deletion rule also covers non-zero on-hand inventory and sales-order history — **only the PO-lines clause is enforced now**; the inventory clause and the sales-history clause (which depends on Module 7, not yet built) are deliberately deferred, not silently dropped.

**Acceptance criteria:** every transition in `docs/PRODUCT-SPEC.md` §10 is enforced server-side, verified by test for every transition including the illegal ones (approve-a-draft, cancel-an-approved); a partial receive leaves the PO in `partially_received` and inventory reflects it immediately, verified against the real `/inventory/stock` and `/inventory/{sku}/ledger` endpoints, not just the PO's own response.

**Tests:** `tests/test_purchase_orders.py` (new, 17 tests) — full create→submit→approve→partially-receive→receive→close lifecycle, every illegal transition rejected, over-receipt rejected without confirmation and accepted with it, edit-after-submit rejected, read-only user denied on every mutating action, supplier/product deletion blocked by open POs and unblocked once cancelled. Full suite (176 tests) + contract tests pass; ruff, ruff format, mypy --strict clean.

**Commit checkpoint:** `feat(purchase-orders): CRUD, status workflow, receiving`

**Known limitations carried forward, not silently dropped:** the non-zero-inventory and sales-order-history clauses of the Product deletion rule (§12) — see the task note above.

* * *

### Backend Module 6 — Customers (new) `[x]`

**Identity-space decision:** `customers` is a fresh, independent identity space — standard autoincrement IDs, real name/email/phone/country — deliberately NOT reconciled with `sales_transactions.customer_id` (the anonymized numeric IDs in the historical dataset, which have no name/contact data to attach). Presenting a customer record with `name: null` for a bare historical ID wouldn't be useful and risks looking like a fabricated identity. If reconciling the two is ever wanted, that's a real product decision for whoever revisits this, not something defaulted here.

**Tasks**

- [x] `customers` table + full CRUD (`GET/POST /customers`, `GET/PUT/DELETE /customers/{id}`), search by name/email
- [ ] `GET /customers/{id}/orders` — still deferred to Module 7 exactly as planned: a freshly-created `customers` row has no historical `sales_transactions` rows keyed to it (different identity space, see above), so there's nothing real to return yet.

**Acceptance criteria:** customer CRUD round-trips correctly and search matches name or email — verified by test.

**Tests:** `tests/test_customers.py` (new) — CRUD round-trip, search by name and by email, 404 on unknown customer, read-only user denied on create. Full suite (181 tests) + contract tests pass; ruff, ruff format, mypy --strict clean.

**Commit checkpoint:** `feat(customers): CRUD`

* * *

### Backend Module 7 — Sales (new: orders, invoices, payments) `[x]`

**Data-model decision (user-confirmed):** `sales_orders`/`invoices`/`payments` are new tables for orders placed through the app going forward. The existing `sales_transactions` table stays completely untouched as the permanent historical record `/analytics/revenue` and the other analytics endpoints continue to read — no FK between the two, and revenue is deliberately **not** reconciled into one combined number. This supersedes this task list's original 4th bullet ("revenue reporting views reconciling with `/analytics/revenue`"), which assumed a merge the user explicitly declined when this module was reached (`docs/stockpilot-gaps.md` #6).

**Tasks**

- [x] `sales_orders` + `sales_order_lines` tables, linked to `customers` (Module 6). Status lifecycle `draft → confirmed → fulfilled`, plus `cancelled` (only from `draft`/`confirmed`) — mirrors the Purchase Order pattern from Module 5 since `docs/PRODUCT-SPEC.md` has no explicit sales-order lifecycle of its own to follow (unlike POs' §10/§12).
- [x] `invoices` table linked to orders (one per order, auto-generated on `confirm`, `total_amount` computed from the order's lines at that moment).
- [x] `payments` table linked to invoices — recorded, not processed: no real payment-gateway integration, matching the same discipline as Module 1's admin-mediated password reset (a real limitation stated plainly, not a half-real payment flow presented as automated). Invoice status (`unpaid`/`partially_paid`/`paid`) is recomputed from the sum of its recorded payments.
- [x] `fulfill` deducts inventory through the exact same `apply_stock_delta` path Modules 4/5 established (now also exposing `get_latest_quantity`, was private) — rejects fulfillment that would drive stock negative (`InsufficientStockError`, reused from Module 4's inventory service, not a duplicate exception type). Writes a real `stock_movements` row (`movement_type='sale'`), the same type the historical dataset's own real sales already use.
- [x] `GET /customers/{id}/orders` — the endpoint deferred in Module 6 is now live, returning that customer's live `sales_orders`.
- [ ] Revenue reporting views reconciling with `/analytics/revenue` — **superseded, not built:** the user's explicit decision (see above) was that these stay two separate eras, never merged. A Sales-module-specific revenue-by-period report over the new live orders was not part of the user's named Module 7 scope ("Orders, Invoices, Payments") and is not built in this pass.

**Acceptance criteria:** a full order → confirm (invoice generated) → fulfill (inventory deducted, real stock movement recorded) → payment (invoice status updates) chain is queryable end to end, verified by test; `/analytics/revenue` is unchanged and continues reading only `sales_transactions`.

**Tests:** `tests/test_sales_orders.py` (new, 12 tests) — full lifecycle, invoice total matches order total, insufficient-stock fulfillment rejected, edit-after-confirm rejected, illegal cancel (post-fulfillment) rejected, partial-then-full payment moves invoice through `partially_paid` to `paid`, customer order-history endpoint, read-only user denied. Full suite (193 tests) + contract tests pass; ruff, ruff format, mypy --strict clean.

**Commit checkpoint:** `feat(sales): orders, invoices, payments`

**Known limitations carried forward, not silently dropped:** no payment-gateway integration (see task note above); no combined/reconciled revenue view across the two eras (by explicit decision, not an oversight); Sales-module-specific revenue-by-period reporting not built.

* * *

### Backend Module 8 — Analytics (extend) `[x]`

**Status:** revenue/profit/turnover/ABC/top-bottom-products/period-comparison were live; supplier rollups and PO-derived KPIs are now too.

**Bug found and fixed while extending this module:** `get_turnover`'s average-stock-on-hand query hadn't been updated for Backend Module 4's location-scoped `stock_levels` (one row per warehouse now, not one per SKU-date) — it was silently averaging per-warehouse fragments instead of summing per SKU-day first. Not yet observable in real numbers (today's data has only the one seeded warehouse, so it was numerically identical), but would have silently produced wrong turnover ratios the moment a second warehouse held stock. Fixed now while touching this file, verified against the unchanged existing turnover test.

**Tasks**

- [x] `GET /analytics/suppliers` — cross-supplier rollup (SKU count, total inventory value, open/total PO count per supplier), distinct from Module 3's per-supplier detail view. Every figure is a real aggregation over already-existing data (Products/Inventory/Purchase Orders) — no new data source.
- [x] `GET /analytics/purchase-order-kpis` — open PO count, plus average days-to-receive derived from the real `stock_movements` rows Module 5's receive endpoint writes (not a separately-tracked timestamp that could drift from what actually happened; `updated_at` alone wasn't usable for this since a subsequent `close` transition also bumps it).

**Acceptance criteria:** every new analytics figure traces to real data, provenance-labeled per `docs/PRODUCT-SPEC.md` §13 — verified by test that each new response includes `_provenance` entries for every numeric field, matching the same `ProvenanceMixin` contract every other analytics endpoint already satisfies.

**Tests:** `tests/test_analytics.py` additions (2 new tests) — supplier rollup reflects real SKU count/inventory value/PO counts and updates correctly as a PO closes; PO KPIs count open POs correctly and compute a real average receive time. Full suite (195 tests) + contract tests pass; ruff, ruff format, mypy --strict clean.

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
