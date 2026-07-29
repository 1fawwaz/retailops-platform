from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user
from database import get_db
from models.user import User
from schemas.forecast import (
    FORECAST_ACCURACY_PROVENANCE,
    SKU_FORECAST_PROVENANCE,
    ForecastAccuracy,
    ForecastRequest,
    SkuForecast,
)
from services.forecast import (
    ForecastModelNotTrainedError,
    SkuForecastResult,
    get_forecasts,
    load_accuracy_report,
)

router = APIRouter(prefix="/forecast", tags=["forecast"])


def _to_sku_forecast(result: SkuForecastResult) -> SkuForecast:
    return SkuForecast(
        sku=result.sku,
        predicted_daily_demand=result.predicted_daily_demand,
        confidence_interval_lower=result.confidence_interval_lower,
        confidence_interval_upper=result.confidence_interval_upper,
        model_used=result.model_used,
        training_window_start=result.training_window_start,
        training_window_end=result.training_window_end,
        data_quality=result.data_quality,
        provenance=SKU_FORECAST_PROVENANCE,
    )


@router.post("/demand", response_model=list[SkuForecast])
def post_forecast_demand(
    request: ForecastRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[SkuForecast]:
    try:
        results = get_forecasts(db, request.skus, request.horizon_days)
    except ForecastModelNotTrainedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return [_to_sku_forecast(result) for result in results]


@router.get("/accuracy", response_model=ForecastAccuracy)
def get_forecast_accuracy(
    _: User = Depends(get_current_user),
) -> ForecastAccuracy:
    try:
        artifact = load_accuracy_report()
    except ForecastModelNotTrainedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return ForecastAccuracy(
        selected_model=artifact.selected_model,
        training_window_start=artifact.training_window_start,
        training_window_end=artifact.training_window_end,
        test_window_start=artifact.test_window_start,
        test_window_end=artifact.test_window_end,
        n_skus_evaluated=artifact.n_skus_evaluated,
        seasonal_naive_mae=artifact.seasonal_naive_mae,
        seasonal_naive_mape=artifact.seasonal_naive_mape,
        moving_average_mae=artifact.moving_average_mae,
        moving_average_mape=artifact.moving_average_mape,
        gbm_mae=artifact.gbm_mae,
        gbm_mape=artifact.gbm_mape,
        provenance=FORECAST_ACCURACY_PROVENANCE,
    )
