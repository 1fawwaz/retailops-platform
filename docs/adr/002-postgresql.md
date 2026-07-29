# ADR 002: PostgreSQL 16, not SQLite, MySQL, or MongoDB

## Status

Accepted — Stage 1 Task 1 (schema and migrations), documented retroactively
at Task 6 once enough of the schema and query layer existed to argue from
actual usage rather than anticipated usage.

## Context

CLAUDE.md pins PostgreSQL 16 in the tech stack table before a single table
exists. This ADR is the "why" behind that pin, argued from what the schema
and query layer actually turned out to need by the time Stage 1 Task 4
(inventory/analytics) and Task 5 (forecasting) were built — not from
speculation about what a retail API might someday need.

Both services (`stockpilot-core`, `retailops-ai`) get their own PostgreSQL
16 instance per ADR 001's separate-databases decision; this ADR is about why
Postgres specifically, not about the two-database topology (that's ADR 001's
job).

## Decision

PostgreSQL 16 for both services, via `docker-compose.yml`'s two
`postgres:16` containers. SQLite is used only as the pytest fixture backend
(`tests/conftest.py`, in-memory, recreated per test) for speed — never in
any deployed environment.

## Why Postgres, argued from what the codebase actually does with it

**Window functions carry real business logic, not just aggregation.**
`services/analytics.py::get_abc_classification` computes ABC inventory
classification via a SQL running total —
`func.sum(revenue).over(order_by=revenue.desc(), rows=(None, 0))` — dividing
by a grand total computed the same way. This is the kind of query where
doing it in Python instead (rank in Python, running-sum in a loop) would be
exactly the "aggregation in Python loops" CLAUDE.md's coding rules forbid.
SQLite has supported window functions since 3.25 (2018), so this alone
wouldn't rule it out, but MySQL didn't get comparable window function
support until 8.0 (2018) either — the real differentiator below is what
happens when the *same* window-function query needs to run identically
across the deployed database and the test fixture.

**Numeric precision for money is load-bearing, not decorative.**
`unit_cost` and `unit_price` are `Numeric(10, 2)` (see
`models/product.py`, `models/sales_transaction.py`), not `Float`. Every
`/analytics/profit` and `/analytics/revenue` figure is a SQL `SUM` over
these columns. Postgres's `NUMERIC` is exact base-10 arithmetic; float-typed
money columns would introduce rounding drift that compounds across
1,039,713 transaction rows and would be genuinely dishonest in a project
whose central invariant is that every number traces back correctly.

**`CHECK` constraints enforce the provenance model at the database layer,
not just in Pydantic.** `models/stock_movement.py` has
`CheckConstraint("provenance IN ('observed', 'derived')")` and
`models/purchase_order.py` has `CheckConstraint("status IN ('received')")`.
This means invariant 3 (untrusted/labelled data) is enforced even against a
raw `INSERT` that skips the API entirely — a defense a schema-less or
weakly-typed store (MongoDB) can't offer without reimplementing constraint
checking in application code, which is one more place for the rule to
silently rot.

**Alembic's Postgres support is the maturity baseline the ecosystem is built
against.** `alembic/env.py` and every migration in `alembic/versions/`
target Postgres-specific DDL behavior (autoincrement semantics, constraint
naming) that Alembic's autogenerate is tuned for first. Targeting SQLite in
production would mean fighting Alembic's assumptions rather than using them.

## Why not SQLite in production (it's still used in tests, deliberately)

SQLite is exactly right for `tests/conftest.py` — an in-memory, per-test,
zero-setup database makes the test suite fast (110 tests in under 15
seconds) and hermetic. But `services/analytics.py::_period_bucket_expr`
exists specifically because SQLite and Postgres disagree on date-bucketing
syntax (`strftime` vs. `to_char`), and week-bucket boundaries between the
two can differ by a day near year boundaries — a real, documented,
non-cosmetic difference between the two engines' date arithmetic. That
function is dialect-branching code the project needs *because* tests run on
SQLite while production runs on Postgres; it would not exist if either engine
were used everywhere. Running SQLite in production would remove the need for
that dialect branch, but at the cost of the exact-numeric and constraint
guarantees above — not a trade this project makes.

## Why not MySQL

Nothing MySQL 8 does is impossible here — the honest reason it wasn't
chosen is that Postgres's `NUMERIC` semantics, richer `CHECK` constraint
expressiveness, and window-function maturity were the safer default for a
project whose core claim is numeric correctness, and there was no
competing requirement (existing MySQL infrastructure, a team's prior MySQL
expertise) pulling the other way. This is a "no reason to pick the
alternative" decision, not a "MySQL is disqualified" one.

## Why not MongoDB or another document store

The data model is relational by nature before a line of derivation logic
exists: `products` references `categories` and `suppliers` by foreign key,
`stock_movements` and `stock_levels` reference `products`, and
`sales_transactions` and `purchase_orders` do too. `services/analytics.py`
and `services/inventory.py` are full of multi-table joins (product ⋈
category, product ⋈ supplier, sales_transaction ⋈ product ⋈ category) that
are exactly what a relational database's join planner exists to do
efficiently. Modeling this as embedded/denormalized documents would mean
either duplicating category and supplier data into every product document
(and reconciling drift by hand) or doing the joins in Python — the latter
being precisely the "aggregation in Python, not SQL" anti-pattern the
coding rules forbid.

## Consequences

- **Every contributor needs a Postgres instance running locally**
  (`docker compose up db-stockpilot db-retailops`) to run anything beyond
  the pytest suite against real dialect behavior — the test suite's SQLite
  fixture doesn't exercise Postgres-only code paths like
  `_period_bucket_expr`'s `to_char` branch (see
  `stockpilot-core/tests/test_contracts.py` and Task 6's coverage notes:
  that one branch is verified by hand against the live database rather than
  through pytest, precisely because of this SQLite/Postgres split).
- **Money columns must stay `Numeric`, never get "simplified" to `Float`**
  for convenience in a future task — that would silently reintroduce
  rounding error into every profit/revenue figure this project reports.
- **Date-bucketing logic must stay dialect-aware.** Any new endpoint that
  buckets by day/week/month has to go through (or extend)
  `_period_bucket_expr` rather than hand-writing a Postgres-only or
  SQLite-only date function, or it will pass in tests and silently misbehave
  in production (or vice versa).

## What would have to be true to reconsider

- **A hosting platform that only offers MySQL or a document store for
  free/cheap tiers**, forcing a Stage 7 deployment trade-off. Nothing in the
  current deployment plan (Railway/Render, per ADR 001) forces this.
- **A future requirement for vector search or embeddings storage** (e.g., if
  RetailOps AI's RAG layer needed similarity search over product
  descriptions) would still argue *for* Postgres, not against it — `pgvector`
  is a Postgres extension, not a reason to switch engines. Nothing in the
  current spec calls for this, so it isn't built, but it's worth noting the
  decision wouldn't need to be revisited if it came up.
- **Measured, not assumed, performance pressure** the current schema and
  query patterns can't meet on Postgres — hasn't happened; the largest table
  (`sales_transactions`, ~1.04M rows) serves every analytics endpoint in this
  project comfortably.
