"""Step (e): suppliers -- a seeded roster, one supplier assigned per SKU.

See docs/data-derivation.md#supplier-assignment.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

N_SUPPLIERS = 15
LEAD_TIME_DAYS_LOW = 3
LEAD_TIME_DAYS_HIGH = 21  # inclusive
RELIABILITY_SCORE_LOW = 0.85
RELIABILITY_SCORE_HIGH = 0.99


def generate_supplier_roster(
    rng: np.random.Generator, n_suppliers: int = N_SUPPLIERS
) -> pd.DataFrame:
    """n_suppliers rows: name, lead_time_days, reliability_score.

    Plain synthetic names ("Supplier 01", ...) rather than invented
    company names, so nothing here could be mistaken for a real
    business. Drawn in that fixed name order for determinism.
    """
    names = [f"Supplier {i:02d}" for i in range(1, n_suppliers + 1)]
    lead_times = rng.integers(LEAD_TIME_DAYS_LOW, LEAD_TIME_DAYS_HIGH + 1, size=n_suppliers)
    reliability_scores = rng.uniform(
        RELIABILITY_SCORE_LOW, RELIABILITY_SCORE_HIGH, size=n_suppliers
    )
    return pd.DataFrame(
        {
            "name": names,
            "lead_time_days": lead_times.tolist(),
            "reliability_score": reliability_scores.tolist(),
        }
    )


def assign_suppliers(skus: list[str], n_suppliers: int, rng: np.random.Generator) -> dict[str, int]:
    """One supplier index (0-based, into the roster) per SKU, drawn uniformly
    at random. Sorts skus internally first, for the same input-order
    independence reason as assign_categories (see categories.py).
    """
    sorted_skus = sorted(skus)
    supplier_indices = rng.integers(0, n_suppliers, size=len(sorted_skus))
    return dict(zip(sorted_skus, supplier_indices.tolist(), strict=True))
