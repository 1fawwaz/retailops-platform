import numpy as np
import pandas as pd

from ml.forecasting import (
    build_daily_series,
    build_feature_frame,
    build_pooled_training_frame,
    build_wide_series,
    confidence_interval,
    gbm_recursive_forecast,
    gbm_recursive_forecast_pooled,
    mean_absolute_error,
    mean_absolute_percentage_error,
    moving_average_forecast,
    residual_std,
    seasonal_naive_forecast,
    train_gbm,
)


def test_build_daily_series_fills_gaps_with_zero() -> None:
    sparse = pd.Series(
        [5.0, 3.0], index=pd.to_datetime(["2026-01-01", "2026-01-04"]), name="quantity"
    )

    series = build_daily_series(sparse, pd.Timestamp("2026-01-06"))

    assert len(series) == 6
    assert series.loc["2026-01-02"] == 0.0
    assert series.loc["2026-01-03"] == 0.0
    assert series.loc["2026-01-04"] == 3.0
    assert series.loc["2026-01-06"] == 0.0


def test_build_daily_series_empty_input_returns_empty() -> None:
    empty = pd.Series([], index=pd.DatetimeIndex([]), dtype=float)

    series = build_daily_series(empty, pd.Timestamp("2026-01-06"))

    assert series.empty


def test_seasonal_naive_repeats_last_period_cyclically() -> None:
    history = pd.Series(
        [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0], index=pd.date_range("2026-01-01", periods=7)
    )

    forecast = seasonal_naive_forecast(history, horizon_days=10, period=7)

    assert list(forecast[:7]) == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    assert list(forecast[7:]) == [1.0, 2.0, 3.0]


def test_seasonal_naive_short_history_still_cycles() -> None:
    history = pd.Series([2.0, 4.0], index=pd.date_range("2026-01-01", periods=2))

    forecast = seasonal_naive_forecast(history, horizon_days=5, period=7)

    assert list(forecast) == [2.0, 4.0, 2.0, 4.0, 2.0]


def test_moving_average_is_flat_mean_of_window() -> None:
    history = pd.Series([10.0, 20.0, 30.0], index=pd.date_range("2026-01-01", periods=3))

    forecast = moving_average_forecast(history, horizon_days=4, window=3)

    assert list(forecast) == [20.0, 20.0, 20.0, 20.0]


def test_moving_average_uses_all_available_days_when_shorter_than_window() -> None:
    history = pd.Series([10.0, 20.0], index=pd.date_range("2026-01-01", periods=2))

    forecast = moving_average_forecast(history, horizon_days=2, window=28)

    assert list(forecast) == [15.0, 15.0]


def test_mean_absolute_error_basic() -> None:
    actual = np.array([10.0, 20.0, 30.0])
    predicted = np.array([12.0, 18.0, 33.0])

    assert mean_absolute_error(actual, predicted) == (2.0 + 2.0 + 3.0) / 3


def test_mean_absolute_percentage_error_ignores_zero_actuals() -> None:
    actual = np.array([0.0, 10.0, 20.0])
    predicted = np.array([5.0, 12.0, 18.0])

    mape = mean_absolute_percentage_error(actual, predicted)

    assert mape == ((2.0 / 10.0) + (2.0 / 20.0)) / 2 * 100


def test_mean_absolute_percentage_error_all_zero_actuals_is_nan() -> None:
    actual = np.array([0.0, 0.0])
    predicted = np.array([1.0, 2.0])

    assert np.isnan(mean_absolute_percentage_error(actual, predicted))


def test_residual_std_and_confidence_interval() -> None:
    actual = np.array([10.0, 12.0, 8.0])
    predicted = np.array([10.0, 10.0, 10.0])

    std = residual_std(actual, predicted)
    lower, upper = confidence_interval(10.0, std)

    assert lower < 10.0 < upper
    assert lower >= 0.0


def test_confidence_interval_clips_lower_bound_at_zero() -> None:
    lower, upper = confidence_interval(1.0, 100.0)

    assert lower == 0.0
    assert upper > 1.0


def _synthetic_history(days: int = 120) -> pd.Series:
    index = pd.date_range("2026-01-01", periods=days, freq="D")
    values = [5.0 + (i % 7) for i in range(days)]
    return pd.Series(values, index=index)


def test_build_feature_frame_drops_rows_without_enough_history() -> None:
    history = _synthetic_history(days=40)

    frame = build_feature_frame(history)

    assert len(frame) == 40 - 28
    assert "lag_1" in frame.columns
    assert "quantity" in frame.columns


def test_build_feature_frame_too_short_returns_empty() -> None:
    history = _synthetic_history(days=10)

    frame = build_feature_frame(history)

    assert frame.empty


def test_train_gbm_and_recursive_forecast_roundtrip() -> None:
    history = _synthetic_history(days=120)
    frame = build_feature_frame(history)

    model = train_gbm(frame)
    forecast = gbm_recursive_forecast(model, history, horizon_days=7)

    assert len(forecast) == 7
    assert (forecast >= 0).all()


def test_build_wide_series_respects_per_sku_first_sale() -> None:
    daily_totals = pd.DataFrame(
        {
            "sku": ["A", "A", "B"],
            "sale_date": pd.to_datetime(["2026-01-01", "2026-01-03", "2026-01-02"]),
            "quantity": [5.0, 2.0, 9.0],
        }
    )

    wide = build_wide_series(daily_totals, pd.Timestamp("2026-01-04"))

    assert pd.isna(wide.loc["2026-01-01", "B"])
    assert wide.loc["2026-01-02", "A"] == 0.0
    assert wide.loc["2026-01-02", "B"] == 9.0
    assert wide.loc["2026-01-04", "A"] == 0.0


def test_pooled_training_frame_matches_single_sku_frame() -> None:
    history = _synthetic_history(days=60)
    single = build_feature_frame(history)

    daily_totals = pd.DataFrame(
        {"sku": ["A"] * len(history), "sale_date": history.index, "quantity": history.to_numpy()}
    )
    wide = build_wide_series(daily_totals, history.index.max())
    pooled = build_pooled_training_frame(wide)

    assert len(pooled) == len(single)
    assert sorted(pooled["quantity"].to_numpy()) == sorted(single["quantity"].to_numpy())


def test_gbm_recursive_forecast_pooled_matches_single_sku() -> None:
    history = _synthetic_history(days=120)
    frame = build_feature_frame(history)
    model = train_gbm(frame)

    single_forecast = gbm_recursive_forecast(model, history, horizon_days=5)

    daily_totals = pd.DataFrame(
        {"sku": ["A"] * len(history), "sale_date": history.index, "quantity": history.to_numpy()}
    )
    wide = build_wide_series(daily_totals, history.index.max())
    pooled_forecast = gbm_recursive_forecast_pooled(model, wide, horizon_days=5)

    np.testing.assert_allclose(pooled_forecast["A"].to_numpy(), single_forecast, rtol=1e-6)
