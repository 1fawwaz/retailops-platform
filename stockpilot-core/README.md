# stockpilot-core

Headless FastAPI + PostgreSQL retail operations API with demand forecasting. See
`docs/BUILD-SPEC.md` for the full specification and `docs/data-derivation.md` for
how the dataset's missing columns (cost price, stock levels, suppliers,
categories) were derived.

## Scope

StockPilot Core is the **environment** half of a two-service system (see
`docs/adr/001-agent-environment-boundary.md`): it owns all business data and
logic behind a versioned HTTP API and has **no UI**. RetailOps AI
(`retailops-ai/`, Stage 2+) is the only user-facing surface. Per the spec's
own scope boundary, this repository deliberately does **not** build: a
frontend, dashboards, PO creation flows, customer management, multi-store
support, or a reporting UI — all of that is the agent service's job, not
this one's.

What it does build, as of Stage 1 (Day 1–5, complete): JWT-authenticated CRUD
on products and suppliers, a reproducible-from-empty ETL pipeline, inventory
and analytics read endpoints, demand forecasting with an honestly-reported
backtest, and a frozen, tested API contract (`docs/api-contract.md`) for
RetailOps AI to build against in Stage 2.

## Data

The dataset is [Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii)
(UCI Machine Learning Repository, CC BY 4.0) — real UK e-commerce
transactions, December 2009 to December 2011, fetched reproducibly via
`scripts/download_data.py` with a checksum. It is gitignored; nothing in
`data/` is committed.

**The raw dataset has no cost price, stock levels, suppliers, or product
categories.** All four are derived by a seeded, deterministic script
(`scripts/run_etl.py`) and labelled `derived` everywhere they appear in API
responses — never presented as if they were part of the original data. The
full derivation methodology, every formula, and measured row counts from the
last real run are in `docs/data-derivation.md`. This disclosure is not
buried in a footnote: it's the reason `docs/data-derivation.md` and the
provenance system (`docs/adr/003-provenance-model.md`) exist at all.

## Honest limitations

- **Forecasting**: the gradient-boosted model does not beat a simple
  moving-average baseline on a real backtest — see Forecasting below for the
  measured numbers. The baseline ships, not the GBM.
- **Forecast confidence intervals** use one global residual standard
  deviation pooled across ~4,800 SKUs of wildly different demand scale, not
  a per-SKU-calibrated interval — deliberately conservative rather than
  falsely precise (see `services/forecast.py`).
- **`/analytics/profit` cost figures** understate true cost for any SKU
  still missing a derived `unit_cost` (documented in
  `services/analytics.py::get_profit`, not silently absorbed).
- **Coverage**: `services/analytics.py`, `api/routers/analytics.py`,
  `services/forecast.py`, `api/routers/forecast.py`, and `ml/forecasting.py`
  measure at 99% statement coverage via `pytest --cov` (Task 6). The one
  uncovered branch (a Postgres-only `to_char` date-bucketing path) was
  verified by hand against the live database instead, since the test suite
  runs on a SQLite fixture for speed — see `docs/adr/002-postgresql.md`.

## API contract

The full endpoint surface is frozen as JSON Schema in
`contracts/stockpilot-api/` and tested against the live app on every
`pytest` run (`tests/test_contracts.py`) — see `docs/api-contract.md` for
what that means and how to re-freeze it after a real change.

## Forecasting

`POST /forecast/demand` and `GET /forecast/accuracy` are backed by
`scripts/train_forecast_model.py`, which backtests three models against a
28-day held-out window (2011-11-12 to 2011-12-09) over 4,801 SKUs with at
least 42 days of pre-holdout sales history, and writes the result to
`ml/artifacts/forecast_accuracy.json`.

**Measured backtest MAE (units/day, lower is better), run 2026-07-29:**

| Model | MAE | MAPE |
|---|---|---|
| Seasonal naive (7-day cycle) | 6.01 | 246.97% |
| **Moving average (28-day window) — selected** | **5.19** | **158.88%** |
| Gradient-boosted (`HistGradientBoostingRegressor`, lag/rolling/calendar features, recursive 28-step forecast) | 6.08 | 250.02% |

**The gradient-boosted model does not beat the moving-average baseline** on
this backtest, so the API serves the moving-average baseline, not the GBM.
The trained GBM artifact is not shipped; `selected_model` in the accuracy
report reflects this. Error compounds over a 28-step recursive forecast on
these series faster than the GBM's extra features earn back, and MAPE is
inflated by many low-volume/intermittent SKUs (days with actual demand near
zero make percentage error explode) — expected behavior for this kind of
retail series, not a bug.

Both MAPE figures are computed excluding days with zero actual demand
(otherwise undefined); this is standard practice for intermittent-demand
series but means MAPE here should be read as "typical relative error on
days with sales," not "typical relative error overall."

**Known limitation:** the confidence interval returned per SKU uses one
global residual standard deviation from the pooled backtest (all 4,801
SKUs' errors together), not a per-SKU-calibrated interval. Demand scale
varies enormously across SKUs (units/day ranges from near-zero to
hundreds), so this interval is deliberately conservative/wide rather than
tight — documented in `services/forecast.py`, not silently smoothed over.

Reproduce with `python scripts/train_forecast_model.py` (requires the
populated database; takes a few minutes).
