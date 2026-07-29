"""Stage 4 Task 4.1: unit tests for the pure, LLM-free derived
computations in tools/derived.py -- no DB, no HTTP, no LLM, so every
formula and edge case is verifiable in isolation from the tool/agent
machinery that wraps these (tests/test_derived_tools.py covers that).
"""

from __future__ import annotations

from tools.derived import (
    StockPosition,
    compute_days_of_cover,
    compute_reorder_timing,
    rank_stockout_risk,
)


def test_days_of_cover_divides_stock_by_predicted_daily_demand() -> None:
    result = compute_days_of_cover(
        sku="85048", quantity_on_hand=100, predicted_daily_demand=10.0, data_quality="ok"
    )

    assert result.days_of_cover == 10.0
    assert result.field_provenance["days_of_cover"] == "predicted"
    assert result.field_provenance["quantity_on_hand"] == "derived"


def test_days_of_cover_is_none_when_predicted_demand_is_zero() -> None:
    """A no_history SKU forecasts zero demand by design (Stage 1's own
    documented behaviour) -- dividing by it is undefined, so this must
    state the gap (None), never report infinity or "fully covered".
    """
    result = compute_days_of_cover(
        sku="99999", quantity_on_hand=50, predicted_daily_demand=0.0, data_quality="no_history"
    )

    assert result.days_of_cover is None
    assert result.data_quality == "no_history"


def test_reorder_timing_computes_days_until_safety_stock_and_reorder_by_days() -> None:
    result = compute_reorder_timing(
        sku="85048",
        quantity_on_hand=100,
        safety_stock=20,
        predicted_daily_demand=10.0,
        lead_time_days=5,
        data_quality="ok",
    )

    # (100 - 20) / 10 = 8 days until safety stock is reached.
    assert result.days_until_safety_stock == 8.0
    # 8 - 5 lead time days = order in 3 days.
    assert result.reorder_by_days == 3.0
    assert result.reorder_now is False


def test_reorder_timing_flags_reorder_now_when_already_overdue() -> None:
    result = compute_reorder_timing(
        sku="85048",
        quantity_on_hand=30,
        safety_stock=20,
        predicted_daily_demand=10.0,
        lead_time_days=5,
        data_quality="ok",
    )

    # (30 - 20) / 10 = 1 day until safety stock; 1 - 5 = -4 -> overdue.
    assert result.days_until_safety_stock == 1.0
    assert result.reorder_by_days == -4.0
    assert result.reorder_now is True


def test_reorder_timing_is_none_when_predicted_demand_is_zero() -> None:
    result = compute_reorder_timing(
        sku="99999",
        quantity_on_hand=50,
        safety_stock=10,
        predicted_daily_demand=0.0,
        lead_time_days=5,
        data_quality="no_history",
    )

    assert result.days_until_safety_stock is None
    assert result.reorder_by_days is None
    assert result.reorder_now is None


def test_rank_stockout_risk_sorts_ascending_by_stock_ratio() -> None:
    positions = [
        StockPosition(sku="A", description=None, quantity_on_hand=80, reorder_point=40),  # 2.0
        StockPosition(sku="B", description=None, quantity_on_hand=10, reorder_point=40),  # 0.25
        StockPosition(sku="C", description=None, quantity_on_hand=40, reorder_point=40),  # 1.0
    ]

    ranking = rank_stockout_risk(positions)

    assert [row.sku for row in ranking.items] == ["B", "C", "A"]
    assert ranking.items[0].stock_ratio == 0.25
    assert ranking.field_provenance["stock_ratio"] == "derived"


def test_rank_stockout_risk_sorts_missing_reorder_point_last_not_dropped() -> None:
    positions = [
        StockPosition(sku="A", description=None, quantity_on_hand=5, reorder_point=None),
        StockPosition(sku="B", description=None, quantity_on_hand=10, reorder_point=40),
    ]

    ranking = rank_stockout_risk(positions)

    assert [row.sku for row in ranking.items] == ["B", "A"]
    assert ranking.items[1].stock_ratio is None


def test_rank_stockout_risk_handles_an_empty_list() -> None:
    """Task 3.6's "empty result set -> a valid answer, not an error"
    invariant applies here too: no low-stock SKUs is a legitimate, fully
    formed (empty) ranking, not an exception.
    """
    ranking = rank_stockout_risk([])

    assert ranking.items == []
    assert ranking.field_provenance
