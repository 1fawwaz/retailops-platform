from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from schemas.provenance import ProvenanceMixin


class ForecastRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"skus": ["85048", "22841"], "horizon_days": 14}]}
    )

    skus: list[str] = Field(min_length=1)
    horizon_days: int = Field(ge=1, le=90)


class SkuForecast(ProvenanceMixin):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "sku": "85048",
                    "predicted_daily_demand": 14.61,
                    "confidence_interval_lower": 0.0,
                    "confidence_interval_upper": 97.19,
                    "model_used": "moving_average",
                    "training_window_start": "2009-12-01",
                    "training_window_end": "2011-12-09",
                    "data_quality": "ok",
                    "_provenance": {
                        "predicted_daily_demand": "predicted",
                        "confidence_interval_lower": "predicted",
                        "confidence_interval_upper": "predicted",
                    },
                    "_derivation_ref": {},
                }
            ]
        },
    )

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
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "selected_model": "moving_average",
                    "training_window_start": "2009-12-01",
                    "training_window_end": "2011-11-11",
                    "test_window_start": "2011-11-12",
                    "test_window_end": "2011-12-09",
                    "n_skus_evaluated": 4801,
                    "seasonal_naive_mae": 6.0136,
                    "seasonal_naive_mape": 246.97,
                    "moving_average_mae": 5.1852,
                    "moving_average_mape": 158.88,
                    "gbm_mae": 6.0781,
                    "gbm_mape": 250.02,
                    "_provenance": {
                        "n_skus_evaluated": "derived",
                        "seasonal_naive_mae": "derived",
                        "seasonal_naive_mape": "derived",
                        "moving_average_mae": "derived",
                        "moving_average_mape": "derived",
                        "gbm_mae": "derived",
                        "gbm_mape": "derived",
                    },
                    "_derivation_ref": {},
                }
            ]
        },
    )

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
