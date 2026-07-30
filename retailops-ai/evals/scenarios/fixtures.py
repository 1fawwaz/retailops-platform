"""Stage 5: shared StockPilot response payload builders reused across
scenario files -- the same MockTransport-JSON-dict pattern every test in
this codebase already uses (tests/test_decision.py,
tests/test_query_coverage.py, ...), collected here once instead of
duplicated ten times.
"""

from __future__ import annotations

import httpx2


def login_response() -> httpx2.Response:
    return httpx2.Response(200, json={"access_token": "t", "token_type": "bearer"})


def product_payload(
    sku: str,
    *,
    quantity_on_hand: int | None = 30,
    safety_stock: int | None = 20,
    reorder_point: int | None = 40,
    supplier_id: int | None = 7,
    unit_cost: float | None = 2.0,
) -> dict[str, object]:
    return {
        "sku": sku,
        "description": f"Widget {sku}",
        "category_id": 3,
        "supplier_id": supplier_id,
        "unit_cost": unit_cost,
        "reorder_point": reorder_point,
        "safety_stock": safety_stock,
        "created_at": "2026-01-01T00:00:00",
        "quantity_on_hand": quantity_on_hand,
        "movement_history": [],
        "_provenance": {
            "sku": "observed",
            "quantity_on_hand": "derived",
            "reorder_point": "derived",
            "safety_stock": "derived",
            "unit_cost": "derived",
        },
        "_derivation_ref": {},
    }


def supplier_payload(
    supplier_id: int = 7, *, lead_time_days: int = 5, name: str = "Acme Wholesale"
) -> dict[str, object]:
    return {
        "id": supplier_id,
        "name": name,
        "lead_time_days": lead_time_days,
        "reliability_score": 0.9,
        "created_at": "2026-01-01T00:00:00",
        "skus": [],
        "_provenance": {"lead_time_days": "derived"},
        "_derivation_ref": {},
    }


def stock_item_payload(
    sku: str, *, quantity_on_hand: int, reorder_point: int | None
) -> dict[str, object]:
    return {
        "sku": sku,
        "description": f"Widget {sku}",
        "category": "Widgets",
        "quantity_on_hand": quantity_on_hand,
        "reorder_point": reorder_point,
        "safety_stock": 10,
        "as_of_date": "2026-07-01",
        "is_low_stock": True,
        "_provenance": {
            "sku": "observed",
            "quantity_on_hand": "derived",
            "reorder_point": "derived",
        },
        "_derivation_ref": {},
    }


def forecast_payload(
    sku: str,
    *,
    predicted_daily_demand: float = 5.0,
    ci_lower: float | None = None,
    ci_upper: float | None = None,
    data_quality: str = "ok",
    training_start: str | None = "2011-01-01",
    training_end: str | None = "2011-11-11",
) -> dict[str, object]:
    return {
        "sku": sku,
        "predicted_daily_demand": predicted_daily_demand,
        "confidence_interval_lower": (
            ci_lower if ci_lower is not None else predicted_daily_demand * 0.8
        ),
        "confidence_interval_upper": (
            ci_upper if ci_upper is not None else predicted_daily_demand * 1.2
        ),
        "model_used": "moving_average" if predicted_daily_demand > 0 else "none",
        "training_window_start": training_start,
        "training_window_end": training_end,
        "data_quality": data_quality,
        "_provenance": {"sku": "observed", "predicted_daily_demand": "predicted"},
        "_derivation_ref": {},
    }


def dead_stock_payload(sku: str, *, quantity_on_hand: int = 20) -> dict[str, object]:
    return {
        "sku": sku,
        "description": f"Widget {sku}",
        "quantity_on_hand": quantity_on_hand,
        "last_movement_date": "2025-01-01T00:00:00",
        "days_since_movement": 200,
        "_provenance": {"sku": "observed", "quantity_on_hand": "derived"},
        "_derivation_ref": {},
    }


def revenue_period_payload(period: str, *, revenue: float, units: int) -> dict[str, object]:
    return {
        "period": period,
        "revenue": revenue,
        "units": units,
        "_provenance": {"revenue": "derived", "units": "observed"},
        "_derivation_ref": {},
    }


def period_comparison_payload(
    *,
    period1_revenue: float = 10000.0,
    period2_revenue: float = 10000.0,
    period1_gross_profit: float = 4000.0,
    period2_gross_profit: float = 4000.0,
    period1_margin: float = 0.4,
    period2_margin: float = 0.4,
) -> dict[str, object]:
    revenue_delta = period2_revenue - period1_revenue
    revenue_delta_pct = (revenue_delta / period1_revenue * 100) if period1_revenue else None
    gross_profit_delta = period2_gross_profit - period1_gross_profit
    gross_profit_delta_pct = (
        (gross_profit_delta / period1_gross_profit * 100) if period1_gross_profit else None
    )
    return {
        "period1_start": "2011-10-01",
        "period1_end": "2011-10-30",
        "period1_revenue": period1_revenue,
        "period1_units": 500,
        "period1_cost": period1_revenue - period1_gross_profit,
        "period1_gross_profit": period1_gross_profit,
        "period1_margin": period1_margin,
        "period2_start": "2011-11-01",
        "period2_end": "2011-11-30",
        "period2_revenue": period2_revenue,
        "period2_units": 400,
        "period2_cost": period2_revenue - period2_gross_profit,
        "period2_gross_profit": period2_gross_profit,
        "period2_margin": period2_margin,
        "revenue_delta": revenue_delta,
        "revenue_delta_pct": revenue_delta_pct,
        "units_delta": -100,
        "units_delta_pct": -20.0,
        "gross_profit_delta": gross_profit_delta,
        "gross_profit_delta_pct": gross_profit_delta_pct,
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


def inventory_valuation_payload(*, total_inventory_value: float = 50000.0) -> dict[str, object]:
    return {
        "by_category": [],
        "total_quantity_on_hand": 1000,
        "total_inventory_value": total_inventory_value,
        "_provenance": {"total_inventory_value": "derived"},
        "_derivation_ref": {},
    }


def top_product_payload(sku: str, *, revenue: float, units: int) -> dict[str, object]:
    return {
        "sku": sku,
        "description": f"Widget {sku}",
        "revenue": revenue,
        "units": units,
        "margin": 0.3,
        "_provenance": {"revenue": "derived", "units": "observed", "margin": "derived"},
        "_derivation_ref": {},
    }
