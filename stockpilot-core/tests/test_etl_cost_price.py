import numpy as np
import pandas as pd

from scripts.etl.cost_price import (
    MARGIN_FACTOR_HIGH,
    MARGIN_FACTOR_LOW,
    compute_unit_costs,
    sample_margin_factors,
)


def test_sample_margin_factors_are_within_range() -> None:
    rng = np.random.default_rng(1)

    factors = sample_margin_factors([1, 2, 3], rng)

    assert set(factors.keys()) == {1, 2, 3}
    assert all(MARGIN_FACTOR_LOW <= v <= MARGIN_FACTOR_HIGH for v in factors.values())


def test_sample_margin_factors_is_deterministic_given_same_seed() -> None:
    factors_a = sample_margin_factors([1, 2, 3], np.random.default_rng(42))
    factors_b = sample_margin_factors([1, 2, 3], np.random.default_rng(42))

    assert factors_a == factors_b


def test_compute_unit_costs_uses_median_price_times_category_margin() -> None:
    transactions_df = pd.DataFrame(
        {
            "sku": ["A1", "A1", "A1"],
            "unit_price": [10.0, 10.0, 20.0],  # median = 10.0
        }
    )
    products_df = pd.DataFrame({"sku": ["A1"], "category_id": [1]})
    margin_factors = {1: 0.6}

    result = compute_unit_costs(transactions_df, products_df, margin_factors)

    assert result["A1"] == 6.0


def test_compute_unit_costs_skips_product_without_category() -> None:
    transactions_df = pd.DataFrame({"sku": ["A1"], "unit_price": [10.0]})
    products_df = pd.DataFrame({"sku": ["A1"], "category_id": [None]})

    result = compute_unit_costs(transactions_df, products_df, margin_factors={})

    assert "A1" not in result


def test_compute_unit_costs_skips_product_without_transactions() -> None:
    transactions_df = pd.DataFrame({"sku": [], "unit_price": []})
    products_df = pd.DataFrame({"sku": ["A1"], "category_id": [1]})

    result = compute_unit_costs(transactions_df, products_df, margin_factors={1: 0.6})

    assert "A1" not in result
