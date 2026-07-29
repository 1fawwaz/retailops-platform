# ADR 003: A four-label provenance model, enforced by a runtime Pydantic validator, never upgraded

## Status

Accepted — Stage 1 Task 2 (`schemas/provenance.py` introduced alongside the
first CRUD endpoints), documented retroactively at Task 6 once the pattern
had been exercised across every response shape through Task 5 (forecasting)
and could be argued from real, varied usage rather than the first case that
motivated it.

## Context

CLAUDE.md invariant 1 requires every numeric claim to carry a provenance
label and states the labels never upgrade. That's a rule on paper; this ADR
is about the concrete mechanism that makes it a rule in code — a shape a
response either satisfies or fails to construct at all, not a convention
reviewers have to remember to check.

The question this ADR answers: given four labels (`observed`, `derived`,
`predicted`, `inferred` — reserved) that describe *where a number came
from*, what's the actual response-schema shape that carries them, and what
enforces that every numeric field has one?

## Decision

Every response schema that carries a business number inherits
`ProvenanceMixin` (`schemas/provenance.py`): a flat `provenance: dict[str,
str]` (serialized as `_provenance`) mapping field name → label, plus an
optional `derivation_ref: dict[str, str]` (serialized as `_derivation_ref`)
mapping field name → a pointer into `docs/data-derivation.md`. A
`model_validator(mode="after")` walks every field on the model at
construction time and raises `ValueError` if any `int`/`float` field
(excluding `bool`, which subclasses `int` in Python but isn't a business
number) has no entry in `provenance`. Two exemption rules keep this from
demanding labels on structural fields that aren't business claims:
`EXEMPT_FIELD_NAMES = {"id", "created_at", "updated_at"}` and any field
name ending in `_id` (foreign keys).

Concretely: a router can't construct `ProductRead(..., provenance={})` and
have it silently serialize with `unit_cost` unlabelled — Pydantic raises at
construction time, in the router, before the response ever reaches a
client. `tests/test_products.py::test_every_numeric_field_has_provenance_entry`
and its equivalents in every other test file assert this holds for real
responses, not just that the validator exists.

## Why a flat dict keyed by field name, not a per-field wrapper object

The alternative considered was wrapping every numeric field individually —
`{"unit_cost": {"value": 2.15, "provenance": "derived"}}` instead of
`{"unit_cost": 2.15, "_provenance": {"unit_cost": "derived"}}`. The wrapper
shape was rejected because:

- **It breaks every consumer that just wants the number.** RetailOps AI's
  tool layer (Stage 2) reads these responses to reason over business data;
  `response["unit_cost"]` being a plain float rather than
  `response["unit_cost"]["value"]` matters at every call site, not just for
  brevity — it's the difference between provenance being metadata *about* an
  otherwise-normal response and provenance *replacing* the response's normal
  shape.
- **A flat sibling dict is trivially diffable and greppable.** Comparing
  `_provenance` across two API versions in a contract diff (see
  `docs/api-contract.md`) is comparing one small dict, not walking every
  field looking for wrapper objects.
- **It matches how OpenAPI/JSON Schema examples read.** Every schema in
  `contracts/stockpilot-api/schemas/` shows the real field values right next
  to a `_provenance` block explaining them — closer to how a human or an
  LLM tool-call log actually wants to read a response than a page of
  `{"value": ..., "provenance": ...}` wrappers would be.

## Why per-row provenance breaks the pattern deliberately in one place

`schemas/product.py::MovementHistoryEntry` (used inside `ProductDetail`'s
`movement_history` list) does **not** inherit `ProvenanceMixin`. Each row
carries its own literal `provenance: str` field instead, copied straight
from the `stock_movements.provenance` database column. This is a
deliberate exception, not an oversight: a single SKU's movement history
mixes `observed` rows (real sales) with `derived` rows (the seeded opening
balance and any injected purchase orders from the stock-ledger replay, see
`docs/data-derivation.md#stock-ledger`) *within the same list*. A
model-level `_provenance` dict can only say "`quantity_delta` is derived"
as one blanket label for the whole response — it cannot say "row 3's
`quantity_delta` is derived but row 7's is observed." Giving each row its
own `provenance` field is the only way to keep the label accurate at the
granularity where the truth actually varies. `ProvenanceMixin`'s validator
does not (and structurally cannot, since it only inspects a model's own
declared fields, not fields nested inside list items) enforce this nested
case — it's covered by construction discipline in
`api/routers/products.py::_to_movement_entry` instead, and by
`tests/test_products.py::test_product_detail_includes_current_stock_and_recent_history`
asserting a real row's label matches its real source.

## Why labels never upgrade, argued from where it actually bites

CLAUDE.md states this as a rule; the codebase has one clean illustration of
why it matters. `services/analytics.py::get_profit` computes
`gross_profit = revenue - cost` where `cost` sums `quantity * unit_cost`
and `unit_cost` is `derived` (Task 3's cost-price derivation, not observed
in the source dataset). Even though `revenue` is aggregated from fully
`observed` `sales_transactions` rows, `gross_profit` is labelled `derived`
throughout `schemas/analytics.py::PROFIT_PERIOD_PROVENANCE` — because one
derived input is enough to make the output no better than derived. The same
logic runs one level further in `services/forecast.py`: every forecast
number is labelled `predicted` (see `schemas/forecast.py::SKU_FORECAST_PROVENANCE`),
even for a SKU whose recent history is entirely `observed`, because the
forecasting *method* itself (a statistical model, not a raw aggregate) is
what makes the output predicted — the label describes the weakest link in
how the number was produced, not the strongest one.

## Why `inferred` is reserved but unused

The label table in CLAUDE.md lists `inferred` as "reserved; avoid." No
schema in this codebase uses it. It exists as a placeholder for a future
case this project hasn't needed — a number derived by pattern-matching or
qualitative judgment rather than a documented formula (`derived`) or a
statistical model (`predicted`). Every number this project actually
produces has fallen cleanly into `observed`, `derived`, or `predicted`; using
`inferred` speculatively for something that's really just an under-documented
`derived` value would be the kind of scope-widening CLAUDE.md's "no
components it doesn't list" rule and "don't design for hypothetical future
requirements" guidance both argue against.

## Consequences

- **Every new response schema with a numeric field must inherit
  `ProvenanceMixin` and populate a matching `provenance` dict, or the
  service will 500 on construction, not silently ship an unlabelled
  number.** This is treated as a feature, not friction — Task 4 and Task 5
  both hit this validator during development and it caught real omissions
  before they reached a test, let alone production.
- **Nested per-row provenance (the `MovementHistoryEntry` case) has to be
  reasoned about by hand per new list-shaped response field** — the mixin
  can't catch a missing per-row label the way it catches a missing
  model-level one. Any future endpoint with the same "mixed provenance
  within one list" shape needs the same deliberate per-row field, not a
  model-level dict papering over it.
- **Provenance labels are part of the frozen contract** (`docs/api-contract.md`):
  changing a field's label from `derived` to `predicted` (or any other
  change) is a contract-breaking change like any other, caught by
  `tests/test_contracts.py`, not a metadata tweak that can slip through
  unreviewed.

## What would have to be true to change this

- **A consumer that genuinely needs per-field wrapper objects** (e.g., a
  strongly-typed client that can't easily correlate two sibling dicts) —
  RetailOps AI's Stage 2 tool layer is the only consumer today, and it reads
  the flat-dict shape directly with no such friction reported.
- **A real case that doesn't fit `observed`/`derived`/`predicted`** would be
  the trigger to finally define what `inferred` means precisely, rather than
  leaving it reserved. No such case has appeared through Stage 1.
