from datetime import date

from pydantic import ConfigDict

from schemas.provenance import ProvenanceMixin


class RevenuePeriod(ProvenanceMixin):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "period": "2011-11",
                    "revenue": 801102.97,
                    "units": 445513,
                    "_provenance": {"revenue": "derived", "units": "derived"},
                    "_derivation_ref": {},
                }
            ]
        },
    )

    period: str
    revenue: float
    units: int


REVENUE_PERIOD_PROVENANCE = {"revenue": "derived", "units": "derived"}


class ProfitPeriod(ProvenanceMixin):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "period": "2011-11",
                    "revenue": 801102.97,
                    "cost": 512705.40,
                    "gross_profit": 288397.57,
                    "margin": 0.36,
                    "_provenance": {
                        "revenue": "derived",
                        "cost": "derived",
                        "gross_profit": "derived",
                        "margin": "derived",
                    },
                    "_derivation_ref": {},
                }
            ]
        },
    )

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
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "category": "Decorations",
                    "units_sold": 4210,
                    "avg_quantity_on_hand": 9860.5,
                    "turnover_ratio": 0.43,
                    "_provenance": {
                        "units_sold": "derived",
                        "avg_quantity_on_hand": "derived",
                        "turnover_ratio": "derived",
                    },
                    "_derivation_ref": {},
                }
            ]
        },
    )

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
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "sku": "85048",
                    "revenue": 45210.30,
                    "cumulative_pct": 0.62,
                    "abc_class": "A",
                    "_provenance": {"revenue": "derived", "cumulative_pct": "derived"},
                    "_derivation_ref": {},
                }
            ]
        },
    )

    sku: str
    revenue: float
    cumulative_pct: float
    abc_class: str


ABC_ROW_PROVENANCE = {"revenue": "derived", "cumulative_pct": "derived"}


class ProductPerformanceRow(ProvenanceMixin):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "sku": "85048",
                    "description": "15CM CHRISTMAS GLASS BALL 20 LIGHTS",
                    "revenue": 45210.30,
                    "units": 21023,
                    "margin": 0.38,
                    "_provenance": {"revenue": "derived", "units": "derived", "margin": "derived"},
                    "_derivation_ref": {},
                }
            ]
        },
    )

    sku: str
    description: str | None
    revenue: float
    units: int
    margin: float | None


PRODUCT_PERFORMANCE_PROVENANCE = {"revenue": "derived", "units": "derived", "margin": "derived"}


class PeriodComparison(ProvenanceMixin):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "period1_start": "2011-10-01",
                    "period1_end": "2011-10-31",
                    "period1_revenue": 750210.10,
                    "period1_units": 410233,
                    "period1_cost": 480134.30,
                    "period1_gross_profit": 270075.80,
                    "period1_margin": 0.36,
                    "period2_start": "2011-11-01",
                    "period2_end": "2011-11-30",
                    "period2_revenue": 801102.97,
                    "period2_units": 445513,
                    "period2_cost": 512705.40,
                    "period2_gross_profit": 288397.57,
                    "period2_margin": 0.36,
                    "revenue_delta": 50892.87,
                    "revenue_delta_pct": 0.068,
                    "units_delta": 35280,
                    "units_delta_pct": 0.086,
                    "gross_profit_delta": 18321.77,
                    "gross_profit_delta_pct": 0.068,
                    "_provenance": {
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
                    },
                    "_derivation_ref": {},
                }
            ]
        },
    )

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
