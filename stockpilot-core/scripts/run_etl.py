"""Run the ETL pipeline: Stage 1 Task 3, steps (a) through (g).

Reproducible from an empty database -- see docs/data-derivation.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from database import get_engine  # noqa: E402
from scripts.etl.clean import clean, load_raw  # noqa: E402
from scripts.etl.load import insert_products, insert_sales_transactions  # noqa: E402
from scripts.etl.product_master import build_product_master  # noqa: E402


def step_a_clean() -> pd.DataFrame:
    print("Step (a): clean")
    print("Loading raw data...")
    raw_df = load_raw()

    cleaned_df, counts = clean(raw_df)
    for key, value in counts.items():
        print(f"  {key}: {value}")
    return cleaned_df


def step_b_product_master(cleaned_df: pd.DataFrame) -> None:
    print("Step (b): product master")
    product_df = build_product_master(cleaned_df)
    print(f"  distinct_products: {len(product_df)}")

    engine = get_engine()
    products_inserted = insert_products(engine, product_df)
    print(f"  products_inserted: {products_inserted}")

    transactions_inserted = insert_sales_transactions(engine, cleaned_df)
    print(f"  sales_transactions_inserted: {transactions_inserted}")


def main() -> None:
    cleaned_df = step_a_clean()
    step_b_product_master(cleaned_df)


if __name__ == "__main__":
    main()
