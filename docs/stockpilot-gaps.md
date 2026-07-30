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
