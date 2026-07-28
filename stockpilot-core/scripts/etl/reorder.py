"""Step (g): reorder_point and safety_stock from demand variability + lead time.

See docs/data-derivation.md#reorder-point.
"""

from __future__ import annotations

import math

import pandas as pd

SERVICE_LEVEL_Z = 1.65  # ~95% one-tailed service level, a standard statistical
# constant for this formula, not a business threshold


def compute_daily_demand_stats(transactions_df: pd.DataFrame) -> pd.DataFrame:
    """transactions_df needs columns sku, invoice_date, quantity.

    Returns one row per sku: avg_daily_demand, demand_std_dev, both computed
    over each SKU's own observed date range (first to last sale), treating
    gap days with no sales as zero demand rather than excluding them.
    """
    df = transactions_df.copy()
    df["sale_date"] = pd.to_datetime(df["invoice_date"]).dt.normalize()

    rows: list[dict[str, object]] = []
    for sku, group in df.groupby("sku", sort=True):
        daily = group.groupby("sale_date")["quantity"].sum()
        first_date = daily.index.min()
        last_date = daily.index.max()
        all_days = pd.date_range(first_date, last_date, freq="D")
        daily_full = daily.reindex(all_days, fill_value=0)

        rows.append(
            {
                "sku": sku,
                "avg_daily_demand": float(daily_full.mean()),
                "demand_std_dev": float(daily_full.std(ddof=0)),
            }
        )

    return pd.DataFrame(rows, columns=["sku", "avg_daily_demand", "demand_std_dev"])


def compute_reorder_points(
    demand_stats_df: pd.DataFrame,
    products_df: pd.DataFrame,
    supplier_lead_times: dict[int, int],
) -> pd.DataFrame:
    """demand_stats_df: sku, avg_daily_demand, demand_std_dev (from above).
    products_df: sku, supplier_id (not nullable at this point in the pipeline).
    supplier_lead_times: supplier_id -> lead_time_days.

    Returns sku, reorder_point, safety_stock (both rounded to int, >= 0).
    """
    merged = demand_stats_df.merge(products_df[["sku", "supplier_id"]], on="sku", how="inner")

    rows: list[dict[str, object]] = []
    for sku_value, avg_demand, std_dev, supplier_id_value in zip(
        merged["sku"],
        merged["avg_daily_demand"],
        merged["demand_std_dev"],
        merged["supplier_id"],
        strict=True,
    ):
        sku = str(sku_value)
        lead_time_days = supplier_lead_times[int(supplier_id_value)]
        avg_daily_demand = float(avg_demand)
        demand_std_dev = float(std_dev)

        safety_stock = max(
            0, math.ceil(SERVICE_LEVEL_Z * demand_std_dev * math.sqrt(lead_time_days))
        )
        reorder_point = max(0, math.ceil(avg_daily_demand * lead_time_days) + safety_stock)

        rows.append({"sku": sku, "reorder_point": reorder_point, "safety_stock": safety_stock})

    return pd.DataFrame(rows, columns=["sku", "reorder_point", "safety_stock"])
