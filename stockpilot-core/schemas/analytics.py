from datetime import date

from pydantic import ConfigDict

from schemas.provenance import ProvenanceMixin


class RevenuePeriod(ProvenanceMixin):
    model_config = ConfigDict(populate_by_name=True)

    period: str
    revenue: float
    units: int


REVENUE_PERIOD_PROVENANCE = {"revenue": "derived", "units": "derived"}


class ProfitPeriod(ProvenanceMixin):
    model_config = ConfigDict(populate_by_name=True)

    period: str
    revenue: float
    cost: float
    gross_profit: float
    margin: float | None


PROFIT_PERIOD_PROVENANCE = {
    "revenue": "derived",
    "cost": "derived",
    "gross_profit": "derived",
    "margin": "derived",
}


class TurnoverRow(ProvenanceMixin):
    model_config = ConfigDict(populate_by_name=True)

    category: str | None
    units_sold: int
    avg_quantity_on_hand: float
    turnover_ratio: float | None


TURNOVER_ROW_PROVENANCE = {
    "units_sold": "derived",
    "avg_quantity_on_hand": "derived",
    "turnover_ratio": "derived",
}


class AbcRow(ProvenanceMixin):
    model_config = ConfigDict(populate_by_name=True)

    sku: str
    revenue: float
    cumulative_pct: float
    abc_class: str


ABC_ROW_PROVENANCE = {"revenue": "derived", "cumulative_pct": "derived"}


class ProductPerformanceRow(ProvenanceMixin):
    model_config = ConfigDict(populate_by_name=True)

    sku: str
    description: str | None
    revenue: float
    units: int
    margin: float | None


PRODUCT_PERFORMANCE_PROVENANCE = {"revenue": "derived", "units": "derived", "margin": "derived"}


class PeriodComparison(ProvenanceMixin):
    model_config = ConfigDict(populate_by_name=True)

    period1_start: date
    period1_end: date
    period1_revenue: float
    period1_units: int
    period1_cost: float
    period1_gross_profit: float
    period1_margin: float | None

    period2_start: date
    period2_end: date
    period2_revenue: float
    period2_units: int
    period2_cost: float
    period2_gross_profit: float
    period2_margin: float | None

    revenue_delta: float
    revenue_delta_pct: float | None
    units_delta: int
    units_delta_pct: float | None
    gross_profit_delta: float
    gross_profit_delta_pct: float | None


PERIOD_COMPARISON_PROVENANCE = {
    "period1_revenue": "derived",
    "period1_units": "derived",
    "period1_cost": "derived",
    "period1_gross_profit": "derived",
    "period1_margin": "derived",
    "period2_revenue": "derived",
    "period2_units": "derived",
    "period2_cost": "derived",
    "period2_gross_profit": "derived",
    "period2_margin": "derived",
    "revenue_delta": "derived",
    "revenue_delta_pct": "derived",
    "units_delta": "derived",
    "units_delta_pct": "derived",
    "gross_profit_delta": "derived",
    "gross_profit_delta_pct": "derived",
}
