from datetime import date, datetime, timedelta
from pathlib import Path

import joblib
import pandas as pd
import pytest
from sqlalchemy.orm import Session

from ml.forecasting import build_feature_frame, train_gbm
from models.product import Product
from models.sales_transaction import SalesTransaction
from services import forecast as forecast_service
from services.forecast import ForecastArtifact, ForecastModelNotTrainedError, forecast_sku

NOW = datetime(2026, 7, 29, 12, 0)


def _artifact(
    *,
    selected_model: str = "moving_average",
    seasonal_naive_mae: float = 10.0,
    moving_average_mae: float = 5.0,
) -> ForecastArtifact:
    return ForecastArtifact(
        selected_model=selected_model,
        residual_std=2.0,
        training_window_start=date(2026, 1, 1),
        training_window_end=date(2026, 6, 1),
        test_window_start=date(2026, 6, 2),
        test_window_end=date(2026, 6, 29),
        n_skus_evaluated=10,
        seasonal_naive_mae=seasonal_naive_mae,
        seasonal_naive_mape=50.0,
        moving_average_mae=moving_average_mae,
        moving_average_mape=40.0,
        gbm_mae=4.0,
        gbm_mape=30.0,
    )


def test_best_baseline_model_picks_lower_mae() -> None:
    assert _artifact(seasonal_naive_mae=3.0, moving_average_mae=5.0).best_baseline_model == (
        "seasonal_naive"
    )
    assert _artifact(seasonal_naive_mae=5.0, moving_average_mae=3.0).best_baseline_model == (
        "moving_average"
    )


def test_load_accuracy_report_raises_when_artifact_missing(tmp_path: Path) -> None:
    missing_path = tmp_path / "does-not-exist.json"
    forecast_service.load_accuracy_report.cache_clear()
    original = forecast_service.ACCURACY_PATH
    forecast_service.ACCURACY_PATH = missing_path
    try:
        with pytest.raises(ForecastModelNotTrainedError):
            forecast_service.load_accuracy_report()
    finally:
        forecast_service.ACCURACY_PATH = original
        forecast_service.load_accuracy_report.cache_clear()


def _seed_sales(db_session: Session, sku: str, days: int) -> None:
    db_session.add(Product(sku=sku, description="Test product"))
    db_session.flush()
    transactions = [
        SalesTransaction(
            invoice=f"INV-{sku}-{day}",
            sku=sku,
            quantity=3 + (day % 4),
            unit_price=5.0,
            country="UK",
            invoice_date=NOW - timedelta(days=days - 1 - day),
        )
        for day in range(days)
    ]
    db_session.add_all(transactions)
    db_session.commit()


def test_forecast_sku_uses_seasonal_naive_when_it_is_the_best_baseline(
    db_session: Session,
) -> None:
    _seed_sales(db_session, "SEASONAL-1", days=40)
    artifact = _artifact(
        selected_model="moving_average", seasonal_naive_mae=1.0, moving_average_mae=5.0
    )

    result = forecast_sku(db_session, "SEASONAL-1", horizon_days=7, artifact=artifact)

    assert result.model_used == "seasonal_naive"


def test_forecast_sku_uses_moving_average_when_it_is_the_best_baseline(
    db_session: Session,
) -> None:
    _seed_sales(db_session, "MOVAVG-1", days=40)
    artifact = _artifact(
        selected_model="moving_average", seasonal_naive_mae=5.0, moving_average_mae=1.0
    )

    result = forecast_sku(db_session, "MOVAVG-1", horizon_days=7, artifact=artifact)

    assert result.model_used == "moving_average"


def test_forecast_sku_uses_gbm_when_selected_and_history_is_sufficient(
    db_session: Session, tmp_path: Path
) -> None:
    _seed_sales(db_session, "GBM-1", days=60)

    training_index = pd.date_range("2020-01-01", periods=120, freq="D")
    training_history = pd.Series([5.0 + (i % 7) for i in range(120)], index=training_index)
    training_frame = build_feature_frame(training_history)
    model = train_gbm(training_frame)
    model_path = tmp_path / "gbm_model.joblib"
    joblib.dump(model, model_path)

    forecast_service.load_gbm_model.cache_clear()
    original_model_path = forecast_service.MODEL_PATH
    forecast_service.MODEL_PATH = model_path
    try:
        artifact = _artifact(selected_model="gbm")
        result = forecast_sku(db_session, "GBM-1", horizon_days=5, artifact=artifact)
        assert result.model_used == "gbm"
        assert result.predicted_daily_demand >= 0
    finally:
        forecast_service.MODEL_PATH = original_model_path
        forecast_service.load_gbm_model.cache_clear()
