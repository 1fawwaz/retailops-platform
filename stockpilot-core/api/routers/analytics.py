from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.deps import get_current_user
from database import get_db
from models.user import User
from schemas.analytics import (
    ABC_ROW_PROVENANCE,
    PERIOD_COMPARISON_PROVENANCE,
    PRODUCT_PERFORMANCE_PROVENANCE,
    PROFIT_PERIOD_PROVENANCE,
    REVENUE_PERIOD_PROVENANCE,
    TURNOVER_ROW_PROVENANCE,
    AbcRow,
    PeriodComparison,
    ProductPerformanceRow,
    ProfitPeriod,
    RevenuePeriod,
    TurnoverRow,
)
from services.analytics import (
    AbcRow as AbcRowData,
)
from services.analytics import (
    PeriodComparisonData,
    ProfitPeriodRow,
    RevenuePeriodRow,
    get_abc_classification,
    get_bottom_products,
    get_period_comparison,
    get_profit,
    get_revenue,
    get_top_products,
    get_turnover,
)
from services.analytics import (
    ProductPerformanceRow as ProductPerformanceRowData,
)
from services.analytics import (
    TurnoverRow as TurnoverRowData,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])

GroupBy = Literal["day", "week", "month", "category"]
Metric = Literal["revenue", "margin", "units"]


def _to_revenue_period(row: RevenuePeriodRow) -> RevenuePeriod:
    return RevenuePeriod(
        period=row.period,
        revenue=row.revenue,
        units=row.units,
        provenance=REVENUE_PERIOD_PROVENANCE,
    )


def _to_profit_period(row: ProfitPeriodRow) -> ProfitPeriod:
    return ProfitPeriod(
        period=row.period,
        revenue=row.revenue,
        cost=row.cost,
        gross_profit=row.gross_profit,
        margin=row.margin,
        provenance=PROFIT_PERIOD_PROVENANCE,
    )


def _to_turnover_row(row: TurnoverRowData) -> TurnoverRow:
    return TurnoverRow(
        category=row.category,
        units_sold=row.units_sold,
        avg_quantity_on_hand=row.avg_quantity_on_hand,
        turnover_ratio=row.turnover_ratio,
        provenance=TURNOVER_ROW_PROVENANCE,
    )


def _to_abc_row(row: AbcRowData) -> AbcRow:
    return AbcRow(
        sku=row.sku,
        revenue=row.revenue,
        cumulative_pct=row.cumulative_pct,
        abc_class=row.abc_class,
        provenance=ABC_ROW_PROVENANCE,
    )


def _to_product_performance_row(row: ProductPerformanceRowData) -> ProductPerformanceRow:
    return ProductPerformanceRow(
        sku=row.sku,
        description=row.description,
        revenue=row.revenue,
        units=row.units,
        margin=row.margin,
        provenance=PRODUCT_PERFORMANCE_PROVENANCE,
    )


def _to_period_comparison(data: PeriodComparisonData) -> PeriodComparison:
    return PeriodComparison(
        period1_start=data.period1_start,
        period1_end=data.period1_end,
        period1_revenue=data.period1.revenue,
        period1_units=data.period1.units,
        period1_cost=data.period1.cost,
        period1_gross_profit=data.period1.gross_profit,
        period1_margin=data.period1.margin,
        period2_start=data.period2_start,
        period2_end=data.period2_end,
        period2_revenue=data.period2.revenue,
        period2_units=data.period2.units,
        period2_cost=data.period2.cost,
        period2_gross_profit=data.period2.gross_profit,
        period2_margin=data.period2.margin,
        revenue_delta=data.revenue_delta,
        revenue_delta_pct=data.revenue_delta_pct,
        units_delta=data.units_delta,
        units_delta_pct=data.units_delta_pct,
        gross_profit_delta=data.gross_profit_delta,
        gross_profit_delta_pct=data.gross_profit_delta_pct,
        provenance=PERIOD_COMPARISON_PROVENANCE,
    )


@router.get("/revenue", response_model=list[RevenuePeriod])
def get_revenue_route(
    group_by: GroupBy = Query(default="day"),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[RevenuePeriod]:
    rows = get_revenue(db, group_by=group_by, start_date=start_date, end_date=end_date)
    return [_to_revenue_period(row) for row in rows]


@router.get("/profit", response_model=list[ProfitPeriod])
def get_profit_route(
    group_by: GroupBy = Query(default="day"),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ProfitPeriod]:
    rows = get_profit(db, group_by=group_by, start_date=start_date, end_date=end_date)
    return [_to_profit_period(row) for row in rows]


@router.get("/turnover", response_model=list[TurnoverRow])
def get_turnover_route(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[TurnoverRow]:
    resolved_end = end_date or date.today()
    resolved_start = start_date or (resolved_end - timedelta(days=90))
    rows = get_turnover(db, start_date=resolved_start, end_date=resolved_end)
    return [_to_turnover_row(row) for row in rows]


@router.get("/abc", response_model=list[AbcRow])
def get_abc_route(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    a_threshold: float = Query(default=0.8, gt=0, lt=1),
    b_threshold: float = Query(default=0.95, gt=0, lt=1),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[AbcRow]:
    rows = get_abc_classification(
        db,
        start_date=start_date,
        end_date=end_date,
        a_threshold=a_threshold,
        b_threshold=b_threshold,
    )
    return [_to_abc_row(row) for row in rows]


@router.get("/top-products", response_model=list[ProductPerformanceRow])
def get_top_products_route(
    metric: Metric = Query(default="revenue"),
    limit: int = Query(default=10, ge=1, le=1000),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ProductPerformanceRow]:
    rows = get_top_products(
        db, metric=metric, limit=limit, start_date=start_date, end_date=end_date
    )
    return [_to_product_performance_row(row) for row in rows]


@router.get("/bottom-products", response_model=list[ProductPerformanceRow])
def get_bottom_products_route(
    metric: Metric = Query(default="revenue"),
    limit: int = Query(default=10, ge=1, le=1000),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ProductPerformanceRow]:
    rows = get_bottom_products(
        db, metric=metric, limit=limit, start_date=start_date, end_date=end_date
    )
    return [_to_product_performance_row(row) for row in rows]


@router.get("/period-comparison", response_model=PeriodComparison)
def get_period_comparison_route(
    period1_start: date = Query(),
    period1_end: date = Query(),
    period2_start: date = Query(),
    period2_end: date = Query(),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PeriodComparison:
    data = get_period_comparison(
        db,
        period1_start=period1_start,
        period1_end=period1_end,
        period2_start=period2_start,
        period2_end=period2_end,
    )
    return _to_period_comparison(data)
