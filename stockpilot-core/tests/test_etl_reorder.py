import math

import pandas as pd

from scripts.etl.reorder import (
    SERVICE_LEVEL_Z,
    compute_daily_demand_stats,
    compute_reorder_points,
)


def _transactions(sku: str, entries: list[tuple[str, int]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "sku": [sku] * len(entries),
            "invoice_date": [pd.Timestamp(date) for date, _ in entries],
            "quantity": [qty for _, qty in entries],
        }
    )


def test_daily_demand_stats_treat_gap_days_as_zero() -> None:
    # daily demand over 2024-01-01..2024-01-04: 10, 20, 0 (gap), 10 -> mean=10
    df = _transactions("A1", [("2024-01-01", 10), ("2024-01-02", 20), ("2024-01-04", 10)])

    stats = compute_daily_demand_stats(df)

    row = stats[stats["sku"] == "A1"].iloc[0]
    assert row["avg_daily_demand"] == 10.0
    assert row["demand_std_dev"] == math.sqrt(50)


def test_reorder_point_matches_documented_formula() -> None:
    demand_stats_df = pd.DataFrame(
        {"sku": ["A1"], "avg_daily_demand": [10.0], "demand_std_dev": [math.sqrt(50)]}
    )
    products_df = pd.DataFrame({"sku": ["A1"], "supplier_id": [1]})
    supplier_lead_times = {1: 5}

    result = compute_reorder_points(demand_stats_df, products_df, supplier_lead_times)

    row = result[result["sku"] == "A1"].iloc[0]
    expected_safety_stock = math.ceil(SERVICE_LEVEL_Z * math.sqrt(50) * math.sqrt(5))
    expected_reorder_point = math.ceil(10.0 * 5) + expected_safety_stock
    assert row["safety_stock"] == expected_safety_stock
    assert row["reorder_point"] == expected_reorder_point


def test_reorder_fields_are_never_negative() -> None:
    demand_stats_df = pd.DataFrame(
        {"sku": ["A1"], "avg_daily_demand": [0.0], "demand_std_dev": [0.0]}
    )
    products_df = pd.DataFrame({"sku": ["A1"], "supplier_id": [1]})

    result = compute_reorder_points(demand_stats_df, products_df, {1: 3})

    row = result.iloc[0]
    assert row["safety_stock"] >= 0
    assert row["reorder_point"] >= 0


def test_higher_lead_time_increases_reorder_point() -> None:
    demand_stats_df = pd.DataFrame(
        {"sku": ["A1"], "avg_daily_demand": [5.0], "demand_std_dev": [2.0]}
    )
    products_df = pd.DataFrame({"sku": ["A1"], "supplier_id": [1]})

    short_lead = compute_reorder_points(demand_stats_df, products_df, {1: 3}).iloc[0]
    long_lead = compute_reorder_points(demand_stats_df, products_df, {1: 20}).iloc[0]

    assert long_lead["reorder_point"] > short_lead["reorder_point"]
