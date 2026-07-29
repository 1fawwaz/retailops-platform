"""Strict input schemas for the StockPilot tool layer (Task 2.3). Each
model is deliberately narrow: only the business parameters an LLM should
reason about, never plumbing like execution_id or a DB session, which
tools/stockpilot_tools.py supplies via closure instead.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

GroupBy = Literal["day", "week", "month", "category"]
PerformanceMetric = Literal["revenue", "margin", "units"]


class ListProductsArgs(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000, description="Max rows to return.")
    offset: int = Field(default=0, ge=0, description="Rows to skip, for pagination.")


class GetProductArgs(BaseModel):
    sku: str = Field(description="The product SKU to look up.")


class ListSuppliersArgs(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000, description="Max rows to return.")
    offset: int = Field(default=0, ge=0, description="Rows to skip, for pagination.")


class GetSupplierArgs(BaseModel):
    supplier_id: int = Field(description="The supplier's numeric ID.")


class GetStockArgs(BaseModel):
    category: str | None = Field(default=None, description="Filter to one category name.")
    low_stock: bool | None = Field(
        default=None, description="If true, only SKUs at or below reorder point."
    )
    search: str | None = Field(
        default=None, description="Free-text search over SKU and description."
    )
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class GetLowStockArgs(BaseModel):
    category: str | None = Field(default=None, description="Filter to one category name.")
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class GetDeadStockArgs(BaseModel):
    days: int = Field(default=90, ge=1, description="No stock movement in at least this many days.")
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class GetSlowMoversArgs(BaseModel):
    window_days: int = Field(
        default=90, ge=1, description="Trailing window to average demand over."
    )
    velocity_threshold: float = Field(
        default=0.2, gt=0, description="Units/day below which a SKU counts as a slow mover."
    )
    limit: int = Field(default=50, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class GetInventoryValuationArgs(BaseModel):
    category: str | None = Field(default=None, description="Restrict to one category name.")


class GetRevenueArgs(BaseModel):
    group_by: GroupBy = Field(
        default="day", description="Bucket revenue by day/week/month/category."
    )
    start_date: date | None = Field(default=None, description="Inclusive start of the date range.")
    end_date: date | None = Field(default=None, description="Inclusive end of the date range.")


class GetProfitArgs(BaseModel):
    group_by: GroupBy = Field(
        default="day", description="Bucket revenue/cost/profit by day/week/month/category."
    )
    start_date: date | None = Field(default=None, description="Inclusive start of the date range.")
    end_date: date | None = Field(default=None, description="Inclusive end of the date range.")


class GetTurnoverArgs(BaseModel):
    start_date: date | None = Field(default=None, description="Inclusive start of the date range.")
    end_date: date | None = Field(default=None, description="Inclusive end of the date range.")


class GetAbcArgs(BaseModel):
    start_date: date | None = Field(default=None, description="Inclusive start of the date range.")
    end_date: date | None = Field(default=None, description="Inclusive end of the date range.")
    a_threshold: float = Field(
        default=0.8, gt=0, lt=1, description="Cumulative revenue share for class A."
    )
    b_threshold: float = Field(
        default=0.95, gt=0, lt=1, description="Cumulative revenue share for class B."
    )


class GetTopProductsArgs(BaseModel):
    metric: PerformanceMetric = Field(
        default="revenue", description="Rank by revenue/margin/units."
    )
    limit: int = Field(default=10, ge=1, le=1000)
    start_date: date | None = Field(default=None, description="Inclusive start of the date range.")
    end_date: date | None = Field(default=None, description="Inclusive end of the date range.")


class GetBottomProductsArgs(BaseModel):
    metric: PerformanceMetric = Field(
        default="revenue", description="Rank by revenue/margin/units."
    )
    limit: int = Field(default=10, ge=1, le=1000)
    start_date: date | None = Field(default=None, description="Inclusive start of the date range.")
    end_date: date | None = Field(default=None, description="Inclusive end of the date range.")


class GetPeriodComparisonArgs(BaseModel):
    period1_start: date = Field(description="Inclusive start of the first (baseline) period.")
    period1_end: date = Field(description="Inclusive end of the first (baseline) period.")
    period2_start: date = Field(description="Inclusive start of the second (comparison) period.")
    period2_end: date = Field(description="Inclusive end of the second (comparison) period.")


class ForecastDemandArgs(BaseModel):
    skus: list[str] = Field(min_length=1, description="SKUs to forecast demand for.")
    horizon_days: int = Field(ge=1, le=90, description="Days ahead to forecast.")


class GetForecastAccuracyArgs(BaseModel):
    pass
