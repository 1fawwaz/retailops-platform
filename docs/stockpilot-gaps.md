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
