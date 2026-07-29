# stockpilot-core

Headless FastAPI + PostgreSQL retail operations API with demand forecasting. See
`docs/BUILD-SPEC.md` for the full specification and `docs/data-derivation.md` for
how the dataset's missing columns (cost price, stock levels, suppliers,
categories) were derived.

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
