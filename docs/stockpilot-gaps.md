# StockPilot Core gaps

Tracks places where `retailops-ai` needed something from StockPilot Core
that didn't exist, or didn't behave the way its frozen contract implies —
logged here per CLAUDE.md §11 rather than silently worked around.

## 1. `datetime` fields are naive, not timezone-aware (found: Stage 2 Task 2.2)

**What happened:** `clients/stockpilot_models.py` is generated from
`contracts/stockpilot-api/versions/v1.json` via `datamodel-code-generator`.
Its default behavior for an OpenAPI `format: date-time` field is Pydantic's
`AwareDatetime` — technically correct per the JSON Schema / RFC3339
`date-time` format, which requires a UTC offset or `Z` suffix. StockPilot
Core's actual JSON responses return naive datetimes with no offset (e.g.
`"2026-07-29T08:28:11.210944"`, not `"...211Z"`), because its SQLAlchemy
models use plain `DateTime` columns (`server_default=func.now()`) without
`timezone=True`. Every generated model validating a live response against
`AwareDatetime` failed with `Input should have timezone info` — caught
during the Task 2.2 live milestone check (`scripts/verify_stockpilot_client.py`),
not by the contract test, which only checks structural drift, not whether
runtime values conform to the format their schema declares.

**Workaround applied (retailops-ai side, not stockpilot-core):**
`--output-datetime-class datetime` was added to the `datamodel-code-generator`
invocation (`make generate-models`), so generated models accept plain
(naive-or-aware) `datetime` instead of requiring `AwareDatetime`. This is
scoped entirely to the already-complete, frozen `stockpilot-core` side —
no changes were made there, since Stage 1 is tagged `stage-1-environment`
and its contract is frozen.

**Why this wasn't fixed at the source instead:** the "correct" long-term
fix is on `stockpilot-core`'s side — either declare `DateTime(timezone=True)`
columns (so Postgres and psycopg return aware datetimes) or explicitly
document that these are UTC-naive and stamp `Z` at serialization time.
That's a schema/migration change to a service whose Stage 1 milestone is
already tagged complete, and re-opening it wasn't this task's job. If a
future task revisits `stockpilot-core`'s datetime columns, re-run
`make generate-models` afterward and this workaround likely becomes
unnecessary (though leaving `--output-datetime-class datetime` costs
nothing either way — it accepts aware datetimes too).

**Impact if unaddressed:** none currently observed beyond the one-time
validation failure above. No code compares timestamps across timezones yet,
so naive-vs-aware hasn't caused an ordering or arithmetic bug. Worth
revisiting if a future task starts doing timezone-sensitive datetime math
against StockPilot timestamps.

## 2. No per-SKU unit price / recent revenue lookup (found: Stage 4 Task 4.3)

**Needed by:** the Decision Engine's `revenue_at_risk = forecast_daily_demand
× unit_price × projected_stockout_days` formula.

**What happened:** `unit_price` exists only inside StockPilot Core's raw
`sales_transaction` table (`models/sales_transaction.py`); no response
model ever exposes it. The only endpoints that expose a derivable price
(`revenue / units`) are `/analytics/top-products` and
`/analytics/bottom-products` — both global rankings bounded by a `limit`
parameter, not filterable by an exact SKU. There is no endpoint that
answers "what is SKU X's recent unit price" directly for an arbitrary SKU.

**Workaround applied (retailops-ai side, decided 2026-07-30, user
confirmed):** `services/pricing.py` fetches `get_top_products` /
`get_bottom_products` with a large limit and computes
`unit_price = revenue / units` for the requested SKU if it appears in
either list. If the SKU appears in neither, `revenue_at_risk` is not
computed for that SKU — the Decision Engine states the gap explicitly
rather than estimating or defaulting a price.

**Impact if unaddressed:** revenue-at-risk coverage is bounded by how
many top/bottom products are fetched, not exhaustive across the whole
catalog — a real, accepted, documented limitation (see
`services/pricing.py`'s own docstring and the honesty section of
`retailops-ai/README.md` once one exists), not a bug.

**Real fix (out of scope, Stage 1 is frozen):** a StockPilot Core
endpoint like `GET /analytics/unit-price/{sku}`, or a `unit_price` /
`avg_selling_price` field added to `ProductRead`/`ProductDetail`,
sourced from the SKU's recent transactions.

## 3. No point-in-time (historical) stock or forecast query (found: Stage 4 Task 4.4)

**Needed by:** Task 4.4's "BACKTEST MODE" — both workflow endpoints
accept an `as_of_date`, and the spec's own wording implies every figure
in the report should reflect what was true as of that past date, not
today.

**What happened:** `stock_levels` genuinely stores a full daily history
per SKU (`models/stock_level.py`, `UniqueConstraint("sku", "as_of_date")`)
— the data exists — but every current inventory endpoint
(`get_stock`/`get_low_stock`/`get_product`/...) is hardcoded to the
`MAX(as_of_date)` row per SKU (`services/inventory.py::_latest_stock_level_subquery`);
none accepts an `as_of_date` query parameter to select a different
snapshot. Forecasting has no as-of capability at all — `forecast_demand`
always trains/scores against all history up to the live request time;
Task 5's own backtest (`scripts/train_forecast_model.py`) was a one-off
offline evaluation script, never a live, queryable "forecast as of a
past date" capability.

The analytics endpoints are the exception: `get_revenue`, `get_profit`,
`get_top_products`, `get_bottom_products`, `get_period_comparison` all
already accept `start_date`/`end_date` and query `sales_transactions`,
which is immutable historical fact — these genuinely can, and do,
reflect a real past period.

**Workaround applied (retailops-ai side, decided 2026-07-30, user
confirmed):** the two workflows are treated differently, honestly:
- `/workflow/business-review/run` (`orchestration/workflows.py`) does a
  REAL backtest — `as_of_date` sets the end of the review period, and
  every revenue/profit/margin/top-bottom/category figure is queried for
  that actual historical window via the date-range-capable analytics
  endpoints above.
- `/workflow/inventory-health/run` can only apply a LABEL — `as_of_date`
  stamps every report/recommendation as
  "Historical simulation as of \<date\>. Not live monitoring." per spec,
  but the underlying stock/reorder/forecast figures are always the
  current live snapshot, since no endpoint can return anything else.
  This is a real, accepted, documented limitation, not silently passed
  off as genuine point-in-time inventory backtesting.

**Real fix (out of scope, Stage 1 is frozen):** an `as_of_date` query
parameter on the inventory endpoints (selecting the nearest
`stock_levels` row on or before that date instead of always the latest),
and a live, queryable "retrain/score as of a past date" forecasting
capability.

## 4. No Purchase Orders, Sales/Orders/Customers, Notifications, Audit Logs, or Settings/Users/Roles endpoints at all (found: `stockpilot-frontend` BUILD.md Stage 0)

**Needed by:** `docs/PRODUCT-SPEC.md` FR-6 (Purchase Orders), FR-7 (Sales),
FR-11 (Notifications), FR-12 (Audit Logs), and FR-13
(Settings/Users/Roles) — five of the fifteen functional requirements the
StockPilot Frontend (ERP) spec defines.

**What happened:** `contracts/stockpilot-api/schemas/` (generated from
StockPilot Core's live OpenAPI export) contains 25 schema files covering
only Products (list/get/create/update — no delete), Suppliers
(list/get/create/update), Inventory (stock/low-stock/dead-stock/
slow-movers/valuation), Analytics (revenue/profit/turnover/abc/top-
bottom-products/period-comparison), Forecasting (forecast-demand/
forecast-accuracy), and Auth (login/register). There is no purchase
order, sales order, customer, notification, audit-log, user-management,
or role-management model or route anywhere in StockPilot Core as it
currently exists. This isn't a contract-doc gap (a real endpoint the
contract forgot to document) — the backend genuinely has none of these
five resources built. StockPilot Core was built as a read-heavy
inventory/analytics/forecasting API (`stockpilot-core/README.md`), not a
transactional ERP backend with order/workflow state.

**Impact on `stockpilot-frontend` BUILD.md:** Stage 0 (this task) is
unaffected — it only needs empty-state pages for every nav item, no real
endpoint wiring. Stage 2 (Inventory) and the read-only parts of Stage 3
(Products) and Stage 4 (Suppliers) are buildable against real data today.
Stage 5 (Purchase Orders), Stage 6 (Sales), and Stage 9 (Settings) cannot
be built against real StockPilot Core data at all in their current form —
building them would mean either inventing a backend that doesn't exist
(explicitly against `CLAUDE.md` §18's "don't invent an API shape... stop
and ask") or building StockPilot Core's missing side first, which is a
separate, substantial backend task outside a frontend repo's scope.

**Not fixed here.** Flagging per convention, not silently deferred: any
session reaching Stage 5/6/9 should stop and confirm with the user
whether to (a) scope those stages down to what's genuinely buildable
(e.g. a Purchase Orders UI against a StockPilot Core PO API that doesn't
exist yet is not buildable at all), (b) build the missing StockPilot Core
endpoints first as its own tracked work, or (c) mark those stages
roadmap-only in the `stockpilot-frontend` README, matching the "ship-thin
vs. ship-long" honesty framing `BUILD.md` already calls for.

**Status (2026-08-14):** resolved. StockPilot Core now exposes
`purchase-orders`, `sales-orders`, `customers`, `notifications`,
`audit-logs`, `users`, `roles`, and `settings` routes — the frozen
contract (`contracts/stockpilot-api/versions/v1.json`) is 66 paths / 88
operations. The `stockpilot-frontend` README no longer lists this as an
open blocker. This entry stays as the historical record of why the
backend build-out was in scope.

## 5. No role/permission field on the User model — RBAC has no backend to enforce it (found: `stockpilot-frontend` BUILD.md Stage 0)

**Needed by:** `docs/PRODUCT-SPEC.md` §6's six-role model (Admin,
Inventory Manager, Procurement, Sales, Analyst, Viewer) and every RBAC
rule in `CLAUDE.md` §12 / `docs/ARCHITECTURE.md` § Authorization that
assumes a permission source exists to check against.

**What happened:** `stockpilot-core/models/user.py`'s `User` model has
exactly five columns: `id`, `email`, `hashed_password`, `is_active`, and
`is_read_only` (a single boolean). There is no `role` column, no
permissions table, no join table of any kind. The JWT StockPilot Core
issues (`services/security.py::create_access_token`) carries only the
user's identity claim — nothing role-shaped to decode. `GET
/me/permissions` (the alternative source `docs/ARCHITECTURE.md` §
Authorization names) does not exist in `contracts/stockpilot-api/`
either. `docs/PRODUCT-SPEC.md` §6 itself already flags this as
provisional and says to confirm before Stage 9 — confirmed now, at
Stage 0, since `lib/rbac/`'s shape depends on it existing at all.

**Workaround applied (`stockpilot-frontend` side, Stage 0):** `lib/rbac/`
implements the `useCan('resource:action')` hook and the six-role
permission MAP from `docs/PRODUCT-SPEC.md` §6 as real, typed,
structurally-correct code — but every authenticated user is currently
assigned a single hardcoded role (`'admin'`, the most-permissive role) at
the point `lib/auth/` establishes a session, since there is no server
field to read a real role from. This is stated plainly in `lib/rbac/`'s
own code comment, not hidden — the hook's *shape* is real and Stage 9
can wire it to a real per-user role the moment one exists server-side;
its *data source* is a placeholder.

**Impact if unaddressed:** every UI-level permission gate in the app is
currently a no-op (everyone sees everyone's view) until this is fixed.
This is explicitly safe only because `CLAUDE.md` §12 already requires
"the frontend must never be the sole enforcement point" — there is no
real authorization boundary here to weaken, because StockPilot Core
itself does not enforce one yet either. Do not treat the UI-level gating
built against this stub as a real security boundary in the meantime.

**Real fix (out of scope for this frontend repo):** a `role` column (or
a proper roles/permissions join) on StockPilot Core's `User` model, a
role claim in the issued JWT or a real `GET /me/permissions` endpoint,
and server-side enforcement of every mutating endpoint per role — a
StockPilot Core change, not a frontend one.

**Status (2026-07-31):** resolved by product decision. `docs/ARCHITECTURE.md`
§7 now specifies a real `roles`/`user_roles` many-to-many model mirroring
`lib/rbac/permissions.ts` exactly, with `GET /me` returning the resolved
role/permission set. Tracked as Backend Module 10 in `docs/BUILD.md`. This
entry is left in place as the historical record of why that decision was
needed, not as an open gap.

## 6. Existing `purchase_orders` and `sales_transactions` tables are not the ERP workflow entities Backend Modules 5/7 need (found: Backend Module 1 survey, 2026-07-31)

**What happened:** while surveying `stockpilot-core/models/` before
starting Backend Module 1 (Authentication), found that a `purchase_orders`
table and a `sales_transactions` table already exist — but neither is the
live, mutable workflow entity `docs/BUILD.md`'s Backend Module 5
(Purchase Orders) and Module 7 (Sales) describe.

- `models/purchase_order.py`'s `PurchaseOrder` is explicitly documented in
  its own docstring as "Simulated purchase orders injected during the
  stock ledger replay wherever stock would otherwise go negative. Entirely
  derived — this dataset has no real purchasing history." Its `status`
  column has a check constraint restricting it to the single value
  `'received'` — there is no Draft/Submitted/Approved/Partially
  Received/Closed lifecycle here at all; every row is a already-completed,
  synthetic backfill event used only to keep the historical stock ledger
  non-negative.
- `models/sales_transaction.py`'s `SalesTransaction` is the real, observed
  (not derived) line-item sales history from the Online Retail II dataset
  — one row per invoice line, no order/invoice/payment grouping, no
  status. This is almost certainly what `/analytics/revenue` and the other
  analytics endpoints already aggregate over.

**Impact:** Backend Module 5 and Module 7 as scoped in `docs/BUILD.md`
("new" `purchase_orders`/`purchase_order_lines` and
`sales_orders`/`invoices`/`payments` tables) would collide on the
`purchase_orders` table name with an existing, semantically incompatible
table, and would introduce a second, parallel source of sales data
alongside the existing observed `sales_transactions` table without a
stated relationship between the two (do new live sales orders ever join
the analytics that currently reads only `sales_transactions`? are the
historical `sales_transactions` ever backfilled as closed sales orders,
or do the two simply coexist as separate eras of data?).

**Not fixed here** — this is flagged, not resolved, per `CLAUDE.md` §11
("stop and ask" rather than silently deciding a product/architecture
question). Will be raised as an explicit decision point when Backend
Module 5/7 planning begins: likely resolution is renaming the new tables
(e.g. `purchase_order_requests` or keeping the ERP workflow table as
`purchase_orders_v2`/similar, TBD) and scoping Module 7's new order/
invoice/payment tables as strictly forward-looking (new orders placed
through the app from go-live onward), leaving `sales_transactions` as the
permanent historical record analytics continues to read — but that is a
product decision, not something to default silently when reached.

**Status (2026-08-01), Purchase Orders half:** resolved by explicit user
decision when Backend Module 5 was reached. The live PO workflow lives in
new tables `purchase_order_requests` / `purchase_order_request_lines`;
the existing synthetic `purchase_orders` table is completely untouched.
See `docs/BUILD.md` Backend Module 5.

**Status (2026-08-01), Sales half:** also resolved by explicit user
decision when Backend Module 7 was reached: new `sales_orders` /
`sales_order_lines` / `invoices` / `payments` tables for orders placed
through the app going forward; the existing `sales_transactions` table
stays completely untouched as the permanent historical record analytics
continues to read. No FK between the two, and revenue is deliberately
not reconciled into one combined figure. See `docs/BUILD.md` Backend
Module 7. Both halves of this gap are now resolved.
