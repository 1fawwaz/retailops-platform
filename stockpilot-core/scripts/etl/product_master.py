"""Step (b): product master from distinct StockCode + Description."""

from __future__ import annotations

import pandas as pd


def _pick_description(descriptions: pd.Series) -> str | None:
    """Most common non-null description; ties broken by first occurrence."""
    non_null = descriptions.dropna()
    if non_null.empty:
        return None

    counts = non_null.value_counts()
    top_candidates = set(counts[counts == counts.max()].index)
    for value in non_null:
        if value in top_candidates:
            return str(value)
    return None  # unreachable: non_null is non-empty, so a candidate always matches


def build_product_master(cleaned_df: pd.DataFrame) -> pd.DataFrame:
    records = [
        {"sku": sku, "description": _pick_description(group["Description"])}
        for sku, group in cleaned_df.groupby("StockCode", sort=True)
    ]
    return pd.DataFrame(records, columns=["sku", "description"])
