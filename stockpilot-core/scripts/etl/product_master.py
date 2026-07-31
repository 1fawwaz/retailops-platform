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


def _pick_from_counts(counts: dict[str, int]) -> str | None:
    """Streaming equivalent of _pick_description: counts is an ordered
    dict (description -> occurrence count) in first-occurrence order, so
    the first key reaching the max count is the same value _pick_description
    would return from the full Series.
    """
    if not counts:
        return None
    max_count = max(counts.values())
    for description, count in counts.items():
        if count == max_count:
            return description
    raise AssertionError("unreachable: counts is non-empty")


class ProductMasterAccumulator:
    """Streaming equivalent of build_product_master: fed one cleaned chunk
    at a time via add_chunk, so the full transaction log is never held in
    memory at once. State is bounded by the number of distinct SKUs
    (thousands), not the number of rows (hundreds of thousands).
    """

    def __init__(self) -> None:
        self._descriptions_by_sku: dict[str, dict[str, int]] = {}

    def add_chunk(self, chunk: pd.DataFrame) -> None:
        for sku, description in zip(chunk["StockCode"], chunk["Description"], strict=True):
            sku_counts = self._descriptions_by_sku.setdefault(str(sku), {})
            if pd.isna(description):
                continue
            description = str(description)
            sku_counts[description] = sku_counts.get(description, 0) + 1

    def build(self) -> pd.DataFrame:
        records = [
            {"sku": sku, "description": _pick_from_counts(counts)}
            for sku, counts in sorted(self._descriptions_by_sku.items())
        ]
        return pd.DataFrame(records, columns=["sku", "description"])
