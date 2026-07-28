"""Run the ETL pipeline: Stage 1 Task 3, steps (a) through (g).

Reproducible from an empty database -- see docs/data-derivation.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
from sqlalchemy import text  # noqa: E402

from database import get_engine, get_session_factory  # noqa: E402
from scripts.etl.categories import assign_categories, load_cluster_labels  # noqa: E402
from scripts.etl.clean import clean, load_raw  # noqa: E402
from scripts.etl.load import (  # noqa: E402
    insert_categories,
    insert_products,
    insert_sales_transactions,
    update_product_categories,
)
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


def step_c_categories() -> None:
    print("Step (c): categories (TF-IDF + KMeans)")
    engine = get_engine()
    with engine.connect() as conn:
        product_df = pd.read_sql(text("SELECT sku, description FROM products ORDER BY sku"), conn)

    assigned = assign_categories(product_df)
    print(f"  categorized_products: {len(assigned)}")
    print(f"  uncategorized_products (no description): {len(product_df) - len(assigned)}")

    session = get_session_factory()()
    try:
        cluster_labels = load_cluster_labels()
        cluster_to_category_id = insert_categories(session, cluster_labels)
        print(f"  categories_inserted: {len(cluster_to_category_id)}")

        sku_to_category_id = {
            str(sku): cluster_to_category_id[int(cluster_id)]
            for sku, cluster_id in zip(assigned["sku"], assigned["cluster_id"], strict=True)
        }
        updated = update_product_categories(session, sku_to_category_id)
        print(f"  products_updated: {updated}")
    finally:
        session.close()


def main() -> None:
    cleaned_df = step_a_clean()
    step_b_product_master(cleaned_df)
    step_c_categories()


if __name__ == "__main__":
    main()
