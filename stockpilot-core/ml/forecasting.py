"""Pure demand-forecasting functions: no DB access anywhere in this
module. Baseline models (seasonal naive, moving average), a
gradient-boosted model on lag/rolling/calendar features, and the
backtest scoring used to compare them. The training script and the
runtime forecast service both import from here, so train-time and
serve-time feature construction can never drift apart.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

LAGS: tuple[int, ...] = (1, 7, 14, 28)
ROLLING_WINDOWS: tuple[int, ...] = (7, 28)
CALENDAR_COLUMNS: tuple[str, ...] = ("day_of_week", "day_of_month", "month", "is_weekend")
FEATURE_COLUMNS: tuple[str, ...] = (
    tuple(f"lag_{lag}" for lag in LAGS)
    + tuple(f"rolling_mean_{w}" for w in ROLLING_WINDOWS)
    + tuple(f"rolling_std_{w}" for w in ROLLING_WINDOWS)
    + CALENDAR_COLUMNS
)
MIN_TRAIN_DAYS_FOR_GBM = max(LAGS + ROLLING_WINDOWS)  # 28: shortest history a feature row needs

CONFIDENCE_Z = 1.96  # ~95% two-tailed interval, a standard statistical constant


def build_daily_series(daily_totals: pd.Series, end_date: pd.Timestamp) -> pd.Series:
    """daily_totals: quantity summed per day, indexed by date, sparse (only
    days with a sale). Reindexes to every calendar day from the series'
    first sale through end_date, zero-filling gaps -- including trailing
    days with no sales, since zero demand is a real observation, not
    missing data.
    """
    if daily_totals.empty:
        return daily_totals
    start = daily_totals.index.min()
    full_index = pd.date_range(start, end_date, freq="D")
    return daily_totals.reindex(full_index, fill_value=0.0).astype(float)


def build_wide_series(daily_totals: pd.DataFrame, end_date: pd.Timestamp) -> pd.DataFrame:
    """daily_totals: long-format columns [sku, sale_date, quantity], sparse
    (only rows where a sale happened). Returns a wide DataFrame indexed by
    every calendar day from the earliest first sale across all SKUs
    through end_date, columns = sku. Values are 0.0 from each SKU's own
    first sale onward (zero demand is observed, not missing) and NaN
    before it (the SKU did not exist yet).
    """
    wide = daily_totals.pivot(index="sale_date", columns="sku", values="quantity")
    full_index = pd.date_range(wide.index.min(), end_date, freq="D")
    wide = wide.reindex(full_index)
    first_sale = daily_totals.groupby("sku")["sale_date"].min()
    for sku in wide.columns:
        mask = wide.index >= first_sale[sku]
        wide.loc[mask, sku] = wide.loc[mask, sku].fillna(0.0)
    return wide


def seasonal_naive_forecast(history: pd.Series, horizon_days: int, period: int = 7) -> np.ndarray:
    """Repeats the last `period` observed days cyclically across the horizon."""
    if len(history) == 0:
        return np.zeros(horizon_days)
    tail = history.iloc[-period:].to_numpy() if len(history) >= period else history.to_numpy()
    return np.array([tail[i % len(tail)] for i in range(horizon_days)], dtype=float)


def moving_average_forecast(history: pd.Series, horizon_days: int, window: int = 28) -> np.ndarray:
    """Flat forecast: the mean of the trailing `window` days (or all
    available days if the history is shorter than the window).
    """
    if len(history) == 0:
        return np.zeros(horizon_days)
    tail = history.iloc[-window:] if len(history) >= window else history
    return np.full(horizon_days, float(tail.mean()))


def mean_absolute_error(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - predicted)))


def mean_absolute_percentage_error(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Standard MAPE. Days where actual==0 are excluded from the
    denominator (otherwise undefined) -- routine for intermittent-demand
    retail series, documented rather than silently smoothed over.
    """
    mask = actual != 0
    if not mask.any():
        return float("nan")
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)


def residual_std(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.std(actual - predicted, ddof=0))


def confidence_interval(point_estimate: float, residual_std_value: float) -> tuple[float, float]:
    lower = max(0.0, point_estimate - CONFIDENCE_Z * residual_std_value)
    upper = point_estimate + CONFIDENCE_Z * residual_std_value
    return lower, upper


def _feature_row(history: pd.Series, target_date: pd.Timestamp) -> dict[str, float]:
    """Feature values for a single future day, computed strictly from data
    strictly before target_date (no leakage).
    """
    row: dict[str, float] = {}
    for lag in LAGS:
        lag_date = target_date - pd.Timedelta(days=lag)
        row[f"lag_{lag}"] = float(history.get(lag_date, 0.0))
    prior = history.loc[: target_date - pd.Timedelta(days=1)]
    for window in ROLLING_WINDOWS:
        tail = prior.iloc[-window:]
        row[f"rolling_mean_{window}"] = float(tail.mean()) if len(tail) else 0.0
        row[f"rolling_std_{window}"] = float(tail.std(ddof=0)) if len(tail) else 0.0
    row["day_of_week"] = float(target_date.dayofweek)
    row["day_of_month"] = float(target_date.day)
    row["month"] = float(target_date.month)
    row["is_weekend"] = float(target_date.dayofweek >= 5)
    return row


def build_feature_frame(history: pd.Series) -> pd.DataFrame:
    """Training rows for a single SKU's daily series: one row per day once
    enough lag/rolling history exists (the first MIN_TRAIN_DAYS_FOR_GBM
    days are dropped), target = that day's quantity. A per-row Python loop
    -- fine for single-SKU runtime scoring, but build_pooled_training_frame
    is the vectorized equivalent used for pooled multi-SKU training.
    """
    if len(history) <= MIN_TRAIN_DAYS_FOR_GBM:
        return pd.DataFrame(columns=[*FEATURE_COLUMNS, "quantity"])
    rows = []
    for i in range(MIN_TRAIN_DAYS_FOR_GBM, len(history)):
        target_date = history.index[i]
        row = _feature_row(history, target_date)
        row["quantity"] = float(history.iloc[i])
        rows.append(row)
    return pd.DataFrame(rows)


def build_pooled_training_frame(wide: pd.DataFrame) -> pd.DataFrame:
    """wide: dates x SKUs, as returned by build_wide_series. Vectorized
    across all columns at once via pandas shift/rolling, unlike
    build_feature_frame's per-row loop -- this is what makes training on
    thousands of SKUs at once tractable.
    """
    lag_frames = {f"lag_{lag}": wide.shift(lag) for lag in LAGS}
    roll_mean_frames = {
        f"rolling_mean_{w}": wide.shift(1).rolling(w).mean() for w in ROLLING_WINDOWS
    }
    roll_std_frames = {
        f"rolling_std_{w}": wide.shift(1).rolling(w).std(ddof=0) for w in ROLLING_WINDOWS
    }
    day_of_week = wide.index.to_series().dt.dayofweek
    day_of_month = wide.index.to_series().dt.day
    month = wide.index.to_series().dt.month
    is_weekend = (day_of_week >= 5).astype(float)

    frames: list[pd.DataFrame] = []
    for sku in wide.columns:
        col = pd.DataFrame({"quantity": wide[sku]})
        for name, frame in {**lag_frames, **roll_mean_frames, **roll_std_frames}.items():
            col[name] = frame[sku]
        col["day_of_week"] = day_of_week.to_numpy(dtype=float)
        col["day_of_month"] = day_of_month.to_numpy(dtype=float)
        col["month"] = month.to_numpy(dtype=float)
        col["is_weekend"] = is_weekend.to_numpy(dtype=float)
        col = col.dropna()
        if not col.empty:
            frames.append(col)
    if not frames:
        return pd.DataFrame(columns=[*FEATURE_COLUMNS, "quantity"])
    return pd.concat(frames, ignore_index=True)


def train_gbm(feature_frame: pd.DataFrame) -> HistGradientBoostingRegressor:
    model = HistGradientBoostingRegressor(random_state=42)
    model.fit(feature_frame[list(FEATURE_COLUMNS)], feature_frame["quantity"])
    return model


def gbm_recursive_forecast(
    model: HistGradientBoostingRegressor, history: pd.Series, horizon_days: int
) -> np.ndarray:
    """Recursive multi-step forecast for a single SKU: predicts one day
    ahead, appends the prediction to build next day's lag/rolling
    features, and repeats. Predictions are clipped at 0 (demand can't be
    negative).
    """
    extended = history.copy()
    predictions = np.zeros(horizon_days)
    current_date = extended.index[-1]
    for h in range(horizon_days):
        current_date = current_date + pd.Timedelta(days=1)
        row = _feature_row(extended, current_date)
        feature_df = pd.DataFrame([row])[list(FEATURE_COLUMNS)]
        pred = max(0.0, float(model.predict(feature_df)[0]))
        predictions[h] = pred
        extended.loc[current_date] = pred
    return predictions


def gbm_recursive_forecast_pooled(
    model: HistGradientBoostingRegressor, wide_train: pd.DataFrame, horizon_days: int
) -> pd.DataFrame:
    """Same recursion as gbm_recursive_forecast, but for every SKU column
    in wide_train at once: one model.predict() call per horizon day (not
    per SKU per day), since each day's features depend only on prior
    days. Returns a DataFrame indexed by forecast date, columns = SKU.
    """
    extended = wide_train.copy()
    last_date = extended.index.max()
    forecast_rows: list[pd.Series] = []
    for h in range(1, horizon_days + 1):
        target_date = last_date + pd.Timedelta(days=h)
        feature_cols: dict[str, pd.Series] = {}
        for lag in LAGS:
            lag_date = target_date - pd.Timedelta(days=lag)
            if lag_date in extended.index:
                feature_cols[f"lag_{lag}"] = extended.loc[lag_date]
            else:
                feature_cols[f"lag_{lag}"] = pd.Series(0.0, index=extended.columns)
        prior = extended.loc[: target_date - pd.Timedelta(days=1)]
        for window in ROLLING_WINDOWS:
            tail = prior.iloc[-window:]
            feature_cols[f"rolling_mean_{window}"] = tail.mean()
            feature_cols[f"rolling_std_{window}"] = tail.std(ddof=0)
        feature_df = pd.DataFrame(feature_cols).reindex(extended.columns).fillna(0.0)
        feature_df["day_of_week"] = float(target_date.dayofweek)
        feature_df["day_of_month"] = float(target_date.day)
        feature_df["month"] = float(target_date.month)
        feature_df["is_weekend"] = float(target_date.dayofweek >= 5)
        preds = np.maximum(model.predict(feature_df[list(FEATURE_COLUMNS)]), 0.0)
        pred_series = pd.Series(preds, index=extended.columns, name=target_date)
        extended.loc[target_date] = pred_series
        forecast_rows.append(pred_series)
    return pd.DataFrame(forecast_rows)
