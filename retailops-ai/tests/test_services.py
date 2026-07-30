"""Stage 4 Task 4.3: unit tests for the pure Decision Engine formulas in
services/ -- no DB, no HTTP, no LLM. tests/test_decision.py covers the
higher-level pipeline (data gathering, the required determinism test).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from clients.stockpilot_models import ProductPerformanceRow
from services.confidence import compute_confidence
from services.order_quantity import compute_recommended_order_qty
from services.pricing import find_unit_price
from services.priority import compute_priority


def _perf_row(sku: str, revenue: float, units: int) -> ProductPerformanceRow:
    return ProductPerformanceRow.model_validate(
        {
            "_provenance": {"revenue": "derived", "units": "observed", "margin": "derived"},
            "sku": sku,
            "description": None,
            "revenue": revenue,
            "units": units,
            "margin": None,
        }
    )


# -- confidence -----------------------------------------------------------


def test_confidence_is_high_for_a_narrow_ci_good_quality_long_history() -> None:
    confidence = compute_confidence(
        confidence_interval_lower=9.0,
        confidence_interval_upper=11.0,
        predicted_daily_demand=10.0,
        data_quality="ok",
        history_days=730,
    )

    # ci_width_factor = 1/(1+0.2) = 0.833; data_quality=1.0; history=1.0
    assert confidence == round(1.0 / 1.2, 4)


def test_confidence_is_low_for_no_history() -> None:
    confidence = compute_confidence(
        confidence_interval_lower=0.0,
        confidence_interval_upper=0.0,
        predicted_daily_demand=0.0,
        data_quality="no_history",
        history_days=0,
    )

    assert confidence == 0.0


def test_confidence_penalizes_thin_history_even_with_a_narrow_ci() -> None:
    good_quality = compute_confidence(
        confidence_interval_lower=9.0,
        confidence_interval_upper=11.0,
        predicted_daily_demand=10.0,
        data_quality="ok",
        history_days=365,
    )
    thin_quality = compute_confidence(
        confidence_interval_lower=9.0,
        confidence_interval_upper=11.0,
        predicted_daily_demand=10.0,
        data_quality="thin_history",
        history_days=365,
    )

    assert thin_quality < good_quality


def test_confidence_is_always_bounded_between_zero_and_one() -> None:
    confidence = compute_confidence(
        confidence_interval_lower=0.0,
        confidence_interval_upper=1000.0,
        predicted_daily_demand=1.0,
        data_quality="ok",
        history_days=10000,
    )

    assert 0.0 <= confidence <= 1.0


# -- priority ---------------------------------------------------------


def test_priority_is_critical_when_revenue_at_risk_is_high() -> None:
    assert compute_priority(revenue_at_risk=6000.0, days_to_stockout=30) == "critical"


def test_priority_is_critical_when_days_to_stockout_is_imminent_even_with_low_revenue() -> None:
    assert compute_priority(revenue_at_risk=10.0, days_to_stockout=1) == "critical"


def test_priority_is_high_between_the_critical_and_high_thresholds() -> None:
    assert compute_priority(revenue_at_risk=1500.0, days_to_stockout=90) == "high"
    assert compute_priority(revenue_at_risk=5.0, days_to_stockout=5) == "high"


def test_priority_is_medium_between_the_high_and_medium_thresholds() -> None:
    assert compute_priority(revenue_at_risk=300.0, days_to_stockout=90) == "medium"
    assert compute_priority(revenue_at_risk=5.0, days_to_stockout=10) == "medium"


def test_priority_is_low_when_neither_dimension_is_concerning() -> None:
    assert compute_priority(revenue_at_risk=5.0, days_to_stockout=90) == "low"


def test_priority_falls_back_to_days_to_stockout_when_revenue_at_risk_is_unknown() -> None:
    """docs/stockpilot-gaps.md#2: revenue_at_risk can be None when no
    unit price was found -- priority must still be computable from
    days_to_stockout alone, not silently skipped or defaulted to "low".
    """
    assert compute_priority(revenue_at_risk=None, days_to_stockout=2) == "critical"
    assert compute_priority(revenue_at_risk=None, days_to_stockout=90) == "low"


# -- order quantity -----------------------------------------------------


def test_recommended_order_qty_covers_lead_time_and_safety_stock() -> None:
    qty = compute_recommended_order_qty(
        predicted_daily_demand=10.0, lead_time_days=7, safety_stock=20, quantity_on_hand=30
    )

    # 10*7 + 20 - 30 = 60
    assert qty == 60


def test_recommended_order_qty_floors_at_zero_when_already_well_stocked() -> None:
    qty = compute_recommended_order_qty(
        predicted_daily_demand=1.0, lead_time_days=3, safety_stock=5, quantity_on_hand=1000
    )

    assert qty == 0


# -- pricing ------------------------------------------------------------


def test_find_unit_price_returns_revenue_over_units_from_top_products() -> None:
    top_tool = MagicMock()
    top_tool.invoke.return_value = [_perf_row("85048", revenue=200.0, units=20)]
    bottom_tool = MagicMock()

    price = find_unit_price(
        top_products_tool=top_tool, bottom_products_tool=bottom_tool, sku="85048", limit=500
    )

    assert price == 10.0
    bottom_tool.invoke.assert_not_called()


def test_find_unit_price_falls_back_to_bottom_products() -> None:
    top_tool = MagicMock()
    top_tool.invoke.return_value = [_perf_row("OTHER", revenue=200.0, units=20)]
    bottom_tool = MagicMock()
    bottom_tool.invoke.return_value = [_perf_row("85048", revenue=5.0, units=5)]

    price = find_unit_price(
        top_products_tool=top_tool, bottom_products_tool=bottom_tool, sku="85048", limit=500
    )

    assert price == 1.0


def test_find_unit_price_returns_none_when_the_sku_appears_in_neither_ranking() -> None:
    top_tool = MagicMock()
    top_tool.invoke.return_value = []
    bottom_tool = MagicMock()
    bottom_tool.invoke.return_value = []

    price = find_unit_price(
        top_products_tool=top_tool, bottom_products_tool=bottom_tool, sku="85048", limit=500
    )

    assert price is None
