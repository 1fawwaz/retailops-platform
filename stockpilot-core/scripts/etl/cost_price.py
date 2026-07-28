"""Step (d): cost price = median unit price per SKU x category margin_factor.

See docs/data-derivation.md#cost-price.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MARGIN_FACTOR_LOW = 0.55
MARGIN_FACTOR_HIGH = 0.80


def sample_margin_factors(category_ids: list[int], rng: np.random.Generator) -> dict[int, float]:
    """One margin_factor per category, drawn in category_id order so the
    draw sequence (and therefore the result) is deterministic given rng's seed.
    """
    return {
        category_id: float(rng.uniform(MARGIN_FACTOR_LOW, MARGIN_FACTOR_HIGH))
        for category_id in sorted(category_ids)
    }


def compute_unit_costs(
    transactions_df: pd.DataFrame,
    products_df: pd.DataFrame,
    margin_factors: dict[int, float],
) -> pd.Series:
    """transactions_df needs columns sku, unit_price.
    products_df needs columns sku, category_id (nullable).

    Returns a Series indexed by sku -> unit_cost, covering only products
    that have both a category (a margin_factor basis) and at least one
    sales transaction (a median price to apply it to). Products missing
    either stay uncovered, so their unit_cost is left null upstream --
    there's no derivation basis to invent one from.
    """
    median_price = transactions_df.groupby("sku")["unit_price"].median()

    unit_costs: dict[str, float] = {}
    for sku_value, category_id in zip(products_df["sku"], products_df["category_id"], strict=True):
        sku = str(sku_value)
        if pd.isna(category_id) or sku not in median_price.index:
            continue
        margin = margin_factors[int(category_id)]
        unit_costs[sku] = round(float(median_price[sku]) * margin, 2)

    return pd.Series(unit_costs, name="unit_cost")
