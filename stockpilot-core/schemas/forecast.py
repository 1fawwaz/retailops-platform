from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from schemas.provenance import ProvenanceMixin


class ForecastRequest(BaseModel):
    skus: list[str] = Field(min_length=1)
    horizon_days: int = Field(ge=1, le=90)


class SkuForecast(ProvenanceMixin):
    model_config = ConfigDict(populate_by_name=True)

    sku: str
    predicted_daily_demand: float
    confidence_interval_lower: float
    confidence_interval_upper: float
    model_used: str
    training_window_start: date | None
    training_window_end: date | None
    data_quality: str


SKU_FORECAST_PROVENANCE = {
    "predicted_daily_demand": "predicted",
    "confidence_interval_lower": "predicted",
    "confidence_interval_upper": "predicted",
}


class ForecastAccuracy(ProvenanceMixin):
    model_config = ConfigDict(populate_by_name=True)

    selected_model: str
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


FORECAST_ACCURACY_PROVENANCE = {
    "n_skus_evaluated": "derived",
    "seasonal_naive_mae": "derived",
    "seasonal_naive_mape": "derived",
    "moving_average_mae": "derived",
    "moving_average_mape": "derived",
    "gbm_mae": "derived",
    "gbm_mape": "derived",
}
