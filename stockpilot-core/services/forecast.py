"""Runtime forecast serving: loads the artifact scripts/train_forecast_model.py
produced (ml/artifacts/forecast_accuracy.json, and gbm_model.joblib if the
GBM won its backtest) and scores requested SKUs against their own current
sales history. Never retrains at request time.
"""

import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ml.forecasting import (
    MIN_TRAIN_DAYS_FOR_GBM,
    build_daily_series,
    confidence_interval,
    gbm_recursive_forecast,
    moving_average_forecast,
    seasonal_naive_forecast,
)
from models.sales_transaction import SalesTransaction

ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "ml" / "artifacts"
ACCURACY_PATH = ARTIFACTS_DIR / "forecast_accuracy.json"
MODEL_PATH = ARTIFACTS_DIR / "gbm_model.joblib"


class ForecastModelNotTrainedError(RuntimeError):
    """Raised when ml/artifacts/forecast_accuracy.json is missing -- the
    training script (scripts/train_forecast_model.py) has never been run
    against this database.
    """


@dataclass(frozen=True)
class ForecastArtifact:
    selected_model: str
    # Pooled across all backtested SKUs, not per-SKU -- demand scale varies
    # enormously across SKUs (near-zero to hundreds of units/day), so the
    # confidence_interval() built from this is deliberately wide/conservative
    # rather than tightly calibrated to any one SKU. Documented limitation,
    # not an oversight -- see README.md#forecasting.
    residual_std: float
    training_window_start: date
    training_window_end: date
    test_window_start: date
    test_window_end: date
    n_skus_evaluated: int
    seasonal_naive_mae: float
    seasonal_naive_mape: float
    moving_average_mae: float
    moving_average_mape: float
    gbm_mae: float
    gbm_mape: float

    @property
    def best_baseline_model(self) -> str:
        """Whichever of the two baselines scored lower MAE in the backtest --
        used as the fallback whenever GBM can't run (it lost overall, or this
        specific SKU's history is too thin for its lag features), regardless
        of which model was ultimately selected.
        """
        if self.seasonal_naive_mae <= self.moving_average_mae:
            return "seasonal_naive"
        return "moving_average"


@lru_cache(maxsize=1)
def load_accuracy_report() -> ForecastArtifact:
    if not ACCURACY_PATH.exists():
        raise ForecastModelNotTrainedError(
            f"{ACCURACY_PATH} not found -- run scripts/train_forecast_model.py first"
        )
    data: dict[str, Any] = json.loads(ACCURACY_PATH.read_text())
    models = data["models"]
    return ForecastArtifact(
        selected_model=data["selected_model"],
        residual_std=data["selected_model_residual_std"],
        training_window_start=date.fromisoformat(data["training_window"]["start"]),
        training_window_end=date.fromisoformat(data["training_window"]["end"]),
        test_window_start=date.fromisoformat(data["test_window"]["start"]),
        test_window_end=date.fromisoformat(data["test_window"]["end"]),
        n_skus_evaluated=data["n_skus_evaluated"],
        seasonal_naive_mae=models["seasonal_naive"]["mae"],
        seasonal_naive_mape=models["seasonal_naive"]["mape"],
        moving_average_mae=models["moving_average"]["mae"],
        moving_average_mape=models["moving_average"]["mape"],
        gbm_mae=models["gbm"]["mae"],
        gbm_mape=models["gbm"]["mape"],
    )


@lru_cache(maxsize=1)
def load_gbm_model() -> HistGradientBoostingRegressor:
    model: HistGradientBoostingRegressor = joblib.load(MODEL_PATH)
    return model


def _sku_daily_totals(db: Session, sku: str) -> pd.Series:
    stmt = (
        select(
            func.date(SalesTransaction.invoice_date).label("sale_date"),
            func.sum(SalesTransaction.quantity).label("quantity"),
        )
        .where(SalesTransaction.sku == sku)
        .group_by(func.date(SalesTransaction.invoice_date))
        .order_by(func.date(SalesTransaction.invoice_date))
    )
    rows = db.execute(stmt).all()
    if not rows:
        return pd.Series([], index=pd.DatetimeIndex([]), dtype=float)
    dates = pd.to_datetime([r.sale_date for r in rows])
    quantities = [float(r.quantity) for r in rows]
    return pd.Series(quantities, index=dates)


@dataclass(frozen=True)
class SkuForecastResult:
    sku: str
    predicted_daily_demand: float
    confidence_interval_lower: float
    confidence_interval_upper: float
    model_used: str
    training_window_start: date | None
    training_window_end: date | None
    data_quality: str


def forecast_sku(
    db: Session, sku: str, horizon_days: int, artifact: ForecastArtifact
) -> SkuForecastResult:
    daily_totals = _sku_daily_totals(db, sku)
    if daily_totals.empty:
        return SkuForecastResult(
            sku=sku,
            predicted_daily_demand=0.0,
            confidence_interval_lower=0.0,
            confidence_interval_upper=0.0,
            model_used="none",
            training_window_start=None,
            training_window_end=None,
            data_quality="no_history",
        )

    end_date = pd.Timestamp(daily_totals.index.max())
    history = build_daily_series(daily_totals, end_date)
    history_days = len(history)
    data_quality = "ok" if history_days >= MIN_TRAIN_DAYS_FOR_GBM else "thin_history"

    if data_quality == "ok" and artifact.selected_model == "gbm" and MODEL_PATH.exists():
        model = load_gbm_model()
        daily_forecast = gbm_recursive_forecast(model, history, horizon_days)
        model_used = "gbm"
    elif artifact.best_baseline_model == "seasonal_naive":
        daily_forecast = seasonal_naive_forecast(history, horizon_days)
        model_used = "seasonal_naive"
    else:
        daily_forecast = moving_average_forecast(history, horizon_days)
        model_used = "moving_average"

    point_estimate = float(daily_forecast.mean())
    lower, upper = confidence_interval(point_estimate, artifact.residual_std)

    return SkuForecastResult(
        sku=sku,
        predicted_daily_demand=point_estimate,
        confidence_interval_lower=lower,
        confidence_interval_upper=upper,
        model_used=model_used,
        training_window_start=history.index.min().date(),
        training_window_end=history.index.max().date(),
        data_quality=data_quality,
    )


def get_forecasts(db: Session, skus: list[str], horizon_days: int) -> list[SkuForecastResult]:
    artifact = load_accuracy_report()
    return [forecast_sku(db, sku, horizon_days, artifact) for sku in skus]
