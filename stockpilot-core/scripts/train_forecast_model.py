"""Stage 1 Task 5: train and backtest the demand-forecasting models.

Baseline first (seasonal naive, moving average), then a gradient-boosted
model on lag/rolling/calendar features -- kept only if it beats the best
baseline on a held-out period. Both scores are written to
ml/artifacts/forecast_accuracy.json regardless of which wins, and the
runtime API (services/forecast.py) reads that file rather than
retraining per request. See README.md#forecasting for the measured
backtest results and why the baseline was kept over the GBM.

Reproducible from the populated database: `python scripts/train_forecast_model.py`.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sqlalchemy import text  # noqa: E402

from database import get_engine  # noqa: E402
from ml.forecasting import (  # noqa: E402
    build_pooled_training_frame,
    build_wide_series,
    gbm_recursive_forecast_pooled,
    mean_absolute_error,
    mean_absolute_percentage_error,
    moving_average_forecast,
    residual_std,
    seasonal_naive_forecast,
    train_gbm,
)

ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "ml" / "artifacts"
ACCURACY_PATH = ARTIFACTS_DIR / "forecast_accuracy.json"
MODEL_PATH = ARTIFACTS_DIR / "gbm_model.joblib"

HOLDOUT_DAYS = 28
MIN_TRAIN_DAYS = 42
SEASONAL_PERIOD = 7
MOVING_AVERAGE_WINDOW = 28


def load_daily_totals() -> pd.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        daily = pd.read_sql(
            text(
                """
                SELECT sku, DATE(invoice_date) AS sale_date, SUM(quantity) AS quantity
                FROM sales_transactions
                GROUP BY sku, DATE(invoice_date)
                ORDER BY sku, sale_date
                """
            ),
            conn,
        )
    daily["sale_date"] = pd.to_datetime(daily["sale_date"])
    daily["quantity"] = daily["quantity"].astype(float)
    return daily


def main() -> None:
    print("Loading daily sales totals...")
    daily = load_daily_totals()
    print(f"  rows: {len(daily)}, skus: {daily['sku'].nunique()}")

    global_max_date = daily["sale_date"].max()
    holdout_start = global_max_date - pd.Timedelta(days=HOLDOUT_DAYS - 1)
    holdout_end = global_max_date
    print(f"  global date range end: {global_max_date.date()}")
    print(f"  holdout window: {holdout_start.date()} .. {holdout_end.date()}")

    print("Building wide daily series (dates x skus)...")
    wide = build_wide_series(daily, global_max_date)

    first_sale = daily.groupby("sku")["sale_date"].min()
    eligibility_cutoff = holdout_start - pd.Timedelta(days=MIN_TRAIN_DAYS)
    eligible_skus = sorted(first_sale[first_sale <= eligibility_cutoff].index)
    print(
        f"  eligible skus for backtest (>= {MIN_TRAIN_DAYS} pre-holdout days): {len(eligible_skus)}"
    )

    wide_train = wide.loc[: holdout_start - pd.Timedelta(days=1), eligible_skus]
    wide_test = wide.loc[holdout_start:holdout_end, eligible_skus]

    print("Scoring baseline models (seasonal naive, moving average)...")
    actual_matrix = wide_test.to_numpy()
    seasonal_predictions = np.zeros_like(actual_matrix)
    moving_avg_predictions = np.zeros_like(actual_matrix)
    for i, sku in enumerate(eligible_skus):
        train_series = wide_train[sku].dropna()
        seasonal_predictions[:, i] = seasonal_naive_forecast(
            train_series, HOLDOUT_DAYS, period=SEASONAL_PERIOD
        )
        moving_avg_predictions[:, i] = moving_average_forecast(
            train_series, HOLDOUT_DAYS, window=MOVING_AVERAGE_WINDOW
        )

    seasonal_mae = mean_absolute_error(actual_matrix, seasonal_predictions)
    seasonal_mape = mean_absolute_percentage_error(actual_matrix, seasonal_predictions)
    moving_avg_mae = mean_absolute_error(actual_matrix, moving_avg_predictions)
    moving_avg_mape = mean_absolute_percentage_error(actual_matrix, moving_avg_predictions)
    print(f"  seasonal_naive: MAE={seasonal_mae:.4f} MAPE={seasonal_mape:.2f}%")
    print(f"  moving_average: MAE={moving_avg_mae:.4f} MAPE={moving_avg_mape:.2f}%")

    if seasonal_mae <= moving_avg_mae:
        best_baseline_name = "seasonal_naive"
        best_baseline_mae = seasonal_mae
        best_baseline_predictions = seasonal_predictions
    else:
        best_baseline_name = "moving_average"
        best_baseline_mae = moving_avg_mae
        best_baseline_predictions = moving_avg_predictions
    print(f"  best baseline: {best_baseline_name} (MAE={best_baseline_mae:.4f})")

    print("Building pooled training features for the GBM...")
    training_frame = build_pooled_training_frame(wide_train)
    print(f"  training rows: {len(training_frame)}")

    print("Training HistGradientBoostingRegressor...")
    model = train_gbm(training_frame)

    print("Generating pooled recursive GBM forecasts for the holdout window...")
    gbm_forecast_df = gbm_recursive_forecast_pooled(model, wide_train, HOLDOUT_DAYS)
    gbm_predictions = gbm_forecast_df[eligible_skus].to_numpy()

    gbm_mae = mean_absolute_error(actual_matrix, gbm_predictions)
    gbm_mape = mean_absolute_percentage_error(actual_matrix, gbm_predictions)
    print(f"  gbm: MAE={gbm_mae:.4f} MAPE={gbm_mape:.2f}%")

    if gbm_mae < best_baseline_mae:
        selected_model = "gbm"
        selected_predictions = gbm_predictions
        print(
            f"GBM beats {best_baseline_name} "
            f"({gbm_mae:.4f} < {best_baseline_mae:.4f}) -- keeping GBM."
        )
    else:
        selected_model = best_baseline_name
        selected_predictions = best_baseline_predictions
        print(
            f"GBM does not beat {best_baseline_name} "
            f"({gbm_mae:.4f} >= {best_baseline_mae:.4f}) -- shipping the baseline."
        )

    selected_residual_std = residual_std(actual_matrix, selected_predictions)

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "trained_at": datetime.now(UTC).isoformat(),
        "training_window": {
            "start": str(wide_train.index.min().date()),
            "end": str(wide_train.index.max().date()),
        },
        "test_window": {"start": str(holdout_start.date()), "end": str(holdout_end.date())},
        "n_skus_evaluated": len(eligible_skus),
        "min_train_days": MIN_TRAIN_DAYS,
        "horizon_days_backtest": HOLDOUT_DAYS,
        "seasonal_period": SEASONAL_PERIOD,
        "moving_average_window": MOVING_AVERAGE_WINDOW,
        "models": {
            "seasonal_naive": {"mae": seasonal_mae, "mape": seasonal_mape},
            "moving_average": {"mae": moving_avg_mae, "mape": moving_avg_mape},
            "gbm": {"mae": gbm_mae, "mape": gbm_mape},
        },
        "selected_model": selected_model,
        "selected_model_residual_std": selected_residual_std,
    }
    ACCURACY_PATH.write_text(json.dumps(report, indent=2))
    print(f"Wrote {ACCURACY_PATH}")

    if selected_model == "gbm":
        joblib.dump(model, MODEL_PATH)
        print(f"Wrote {MODEL_PATH}")
    elif MODEL_PATH.exists():
        MODEL_PATH.unlink()
        print(f"Removed stale {MODEL_PATH} (baseline won this run)")


if __name__ == "__main__":
    main()
