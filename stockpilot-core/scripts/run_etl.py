"""Run the ETL pipeline: Stage 1 Task 3, steps (a) through (g).

Reproducible from an empty database -- see docs/data-derivation.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sqlalchemy import text  # noqa: E402

from database import get_engine, get_session_factory  # noqa: E402
from scripts.etl.categories import assign_categories, load_cluster_labels  # noqa: E402
from scripts.etl.clean import clean, load_raw  # noqa: E402
from scripts.etl.cost_price import compute_unit_costs, sample_margin_factors  # noqa: E402
from scripts.etl.load import (  # noqa: E402
    insert_categories,
    insert_products,
    insert_purchase_orders,
    insert_sales_transactions,
    insert_stock_levels,
    insert_stock_movements,
    insert_suppliers,
    update_product_categories,
    update_product_suppliers,
    update_product_unit_costs,
)
from scripts.etl.product_master import build_product_master  # noqa: E402
from scripts.etl.random_seed import create_rng  # noqa: E402
from scripts.etl.stock_ledger import replay_stock_ledger  # noqa: E402
from scripts.etl.suppliers import (  # noqa: E402
    N_SUPPLIERS,
    assign_suppliers,
    generate_supplier_roster,
)


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


def step_d_cost_price(rng: np.random.Generator) -> None:
    print("Step (d): cost price")
    engine = get_engine()
    with engine.connect() as conn:
        products_df = pd.read_sql(text("SELECT sku, category_id FROM products"), conn)
        transactions_df = pd.read_sql(text("SELECT sku, unit_price FROM sales_transactions"), conn)

    category_ids = [int(c) for c in products_df["category_id"].dropna().unique()]
    margin_factors = sample_margin_factors(category_ids, rng)
    print(f"  categories_with_margin_factor: {len(margin_factors)}")

    unit_costs = compute_unit_costs(transactions_df, products_df, margin_factors)
    print(f"  products_with_unit_cost: {len(unit_costs)}")

    sku_to_unit_cost = {str(sku): float(cost) for sku, cost in unit_costs.items()}

    session = get_session_factory()()
    try:
        updated = update_product_unit_costs(session, sku_to_unit_cost)
        print(f"  products_updated: {updated}")
    finally:
        session.close()


def step_e_suppliers(rng: np.random.Generator) -> None:
    print("Step (e): suppliers")
    engine = get_engine()
    with engine.connect() as conn:
        skus = pd.read_sql(text("SELECT sku FROM products"), conn)["sku"].tolist()

    roster_df = generate_supplier_roster(rng)

    session = get_session_factory()()
    try:
        supplier_ids = insert_suppliers(session, roster_df)
        print(f"  suppliers_inserted: {len(supplier_ids)}")

        sku_to_supplier_index = assign_suppliers(skus, N_SUPPLIERS, rng)
        sku_to_supplier_id = {
            sku: supplier_ids[index] for sku, index in sku_to_supplier_index.items()
        }
        updated = update_product_suppliers(session, sku_to_supplier_id)
        print(f"  products_updated: {updated}")
    finally:
        session.close()


def step_f_stock_ledger() -> None:
    print("Step (f): stock ledger")
    engine = get_engine()
    with engine.connect() as conn:
        transactions_df = pd.read_sql(
            text("SELECT sku, invoice_date, quantity FROM sales_transactions"), conn
        )
        products_df = pd.read_sql(text("SELECT sku, supplier_id FROM products"), conn)

    sku_to_supplier_id = {
        str(sku): int(supplier_id)
        for sku, supplier_id in zip(products_df["sku"], products_df["supplier_id"], strict=True)
    }

    result = replay_stock_ledger(transactions_df, sku_to_supplier_id)
    print(f"  stock_movements: {len(result.stock_movements)}")
    print(f"  stock_levels: {len(result.stock_levels)}")
    print(f"  purchase_orders: {len(result.purchase_orders)}")

    po_inserted = insert_purchase_orders(engine, result.purchase_orders)
    print(f"  purchase_orders_inserted: {po_inserted}")

    movements_inserted = insert_stock_movements(engine, result.stock_movements)
    print(f"  stock_movements_inserted: {movements_inserted}")

    levels_inserted = insert_stock_levels(engine, result.stock_levels)
    print(f"  stock_levels_inserted: {levels_inserted}")


def main() -> None:
    rng = create_rng()

    cleaned_df = step_a_clean()
    step_b_product_master(cleaned_df)
    step_c_categories()
    step_d_cost_price(rng)
    step_e_suppliers(rng)
    step_f_stock_ledger()


if __name__ == "__main__":
    main()
