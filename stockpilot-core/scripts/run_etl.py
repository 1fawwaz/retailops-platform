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
from scripts.etl.clean import DEFAULT_CHUNK_SIZE, clean, iter_raw_chunks  # noqa: E402
from scripts.etl.cost_price import compute_unit_costs, sample_margin_factors  # noqa: E402
from scripts.etl.dataset_scope import SkuVolumeCounter  # noqa: E402
from scripts.etl.load import (  # noqa: E402
    insert_categories,
    insert_products,
    insert_purchase_orders,
    insert_sales_transactions,
    insert_stock_levels,
    insert_stock_movements,
    insert_suppliers,
    update_product_categories,
    update_product_reorder_fields,
    update_product_suppliers,
    update_product_unit_costs,
)
from scripts.etl.product_master import ProductMasterAccumulator  # noqa: E402
from scripts.etl.random_seed import create_rng  # noqa: E402
from scripts.etl.reorder import compute_daily_demand_stats, compute_reorder_points  # noqa: E402
from scripts.etl.stock_ledger import replay_stock_ledger  # noqa: E402
from scripts.etl.suppliers import (  # noqa: E402
    N_SUPPLIERS,
    assign_suppliers,
    generate_supplier_roster,
)
from settings import get_settings  # noqa: E402


def step_a_and_b_clean_and_product_master() -> None:
    """Steps (a) clean + (b) product master, in two streaming passes over
    the raw workbook so the ~1M-row dataset is never held in memory as one
    DataFrame. The first attempt at this step held the full raw workbook in
    memory via pd.read_excel(sheet_name=None) and was OOM-killed on Railway
    before a single row reached the database -- see iter_raw_chunks's own
    docstring. Two passes are required (rather than one) because
    sales_transactions.sku has a foreign key to products.sku: every product
    must exist before any transaction referencing it can be inserted.

    If ETL_MAX_TRANSACTIONS is set (see docs/data-derivation.md#demo-dataset-scope),
    only the top SKUs by transaction volume -- covering up to that many
    transactions -- are kept, each with its full observed history. This is a
    disclosed, deliberate scope reduction for storage-constrained deployments,
    not a change to the derivation logic itself: every kept row is cleaned and
    derived exactly as documented, just over fewer products.
    """
    print("Step (a)+(b): clean, product master, sales transactions (streaming)")
    max_transactions = get_settings().etl_max_transactions
    if max_transactions is not None:
        print(
            f"  ETL_MAX_TRANSACTIONS={max_transactions}: loading a scoped subset, "
            "not the full dataset -- see docs/data-derivation.md#demo-dataset-scope"
        )

    print("Pass 1/2: accumulating product master...")
    total_counts: dict[str, int] = {}
    accumulator = ProductMasterAccumulator()
    sku_volume_counter = SkuVolumeCounter()
    for i, raw_chunk in enumerate(iter_raw_chunks(chunk_size=DEFAULT_CHUNK_SIZE), start=1):
        cleaned_chunk, counts = clean(raw_chunk)
        for key, value in counts.items():
            total_counts[key] = total_counts.get(key, 0) + value
        accumulator.add_chunk(cleaned_chunk)
        sku_volume_counter.add_chunk(cleaned_chunk)
        print(f"  chunk {i}: {len(raw_chunk)} raw -> {len(cleaned_chunk)} cleaned")
    for key, value in total_counts.items():
        print(f"  {key}: {value}")

    product_df = accumulator.build()
    selected_skus: set[str] | None = None
    if max_transactions is not None:
        selected_skus = sku_volume_counter.top_skus_by_target_volume(max_transactions)
        product_df = product_df[product_df["sku"].isin(selected_skus)].reset_index(drop=True)
        print(f"  demo scope: keeping {len(selected_skus)} of the full distinct-SKU count")
    print(f"  distinct_products: {len(product_df)}")

    engine = get_engine()
    products_inserted = insert_products(engine, product_df)
    print(f"  products_inserted: {products_inserted}")

    print("Pass 2/2: inserting sales transactions...")
    transactions_inserted = 0
    checkpoint_every_n_chunks = 5
    for i, raw_chunk in enumerate(iter_raw_chunks(chunk_size=DEFAULT_CHUNK_SIZE), start=1):
        cleaned_chunk, _ = clean(raw_chunk)
        if selected_skus is not None:
            cleaned_chunk = cleaned_chunk[cleaned_chunk["StockCode"].isin(selected_skus)]
        transactions_inserted += insert_sales_transactions(engine, cleaned_chunk)
        print(f"  chunk {i}: sales_transactions_inserted so far = {transactions_inserted}")
        if i % checkpoint_every_n_chunks == 0:
            checkpoint()
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


STOCK_LEDGER_BATCH_SIZE = 500


def step_f_stock_ledger() -> None:
    """Processes and inserts in batches of SKUs rather than building one
    ~2.3M-row result in memory before a single bulk insert -- the first
    attempt at this step was killed partway through (likely memory pressure
    from holding every SKU's full daily history at once); batching bounds
    peak memory and gives incremental progress instead of an all-or-nothing
    multi-million-row insert.
    """
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
    all_skus = sorted(sku_to_supplier_id)

    total_movements = 0
    total_levels = 0
    total_purchase_orders = 0

    for start in range(0, len(all_skus), STOCK_LEDGER_BATCH_SIZE):
        batch_skus = set(all_skus[start : start + STOCK_LEDGER_BATCH_SIZE])
        batch_transactions = transactions_df[transactions_df["sku"].isin(batch_skus)]
        batch_supplier_map = {sku: sku_to_supplier_id[sku] for sku in batch_skus}

        result = replay_stock_ledger(batch_transactions, batch_supplier_map)

        total_purchase_orders += insert_purchase_orders(engine, result.purchase_orders)
        total_movements += insert_stock_movements(engine, result.stock_movements)
        total_levels += insert_stock_levels(engine, result.stock_levels)

        print(
            f"  batch {start // STOCK_LEDGER_BATCH_SIZE + 1}: "
            f"{len(batch_skus)} skus, running totals -- "
            f"movements={total_movements} levels={total_levels} pos={total_purchase_orders}"
        )
        checkpoint()

    print(f"  stock_movements_inserted: {total_movements}")
    print(f"  stock_levels_inserted: {total_levels}")
    print(f"  purchase_orders_inserted: {total_purchase_orders}")


def step_g_reorder() -> None:
    print("Step (g): reorder_point and safety_stock")
    engine = get_engine()
    with engine.connect() as conn:
        transactions_df = pd.read_sql(
            text("SELECT sku, invoice_date, quantity FROM sales_transactions"), conn
        )
        products_df = pd.read_sql(text("SELECT sku, supplier_id FROM products"), conn)
        suppliers_df = pd.read_sql(text("SELECT id, lead_time_days FROM suppliers"), conn)

    supplier_lead_times = {
        int(supplier_id): int(lead_time_days)
        for supplier_id, lead_time_days in zip(
            suppliers_df["id"], suppliers_df["lead_time_days"], strict=True
        )
    }

    demand_stats_df = compute_daily_demand_stats(transactions_df)
    reorder_df = compute_reorder_points(demand_stats_df, products_df, supplier_lead_times)
    print(f"  products_with_reorder_fields: {len(reorder_df)}")

    session = get_session_factory()()
    try:
        updated = update_product_reorder_fields(session, reorder_df)
        print(f"  products_updated: {updated}")
    finally:
        session.close()


def checkpoint() -> None:
    """Forces Postgres to recycle WAL segments now rather than waiting for
    its own checkpoint_timeout. On a storage-constrained volume, WAL from a
    write-heavy step can otherwise sit around consuming disk long after the
    step's own data has committed -- found live: 192MB of WAL remained after
    inserting only 55% of sales_transactions, on a 500MB volume.
    """
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("CHECKPOINT"))
        conn.commit()


def main() -> None:
    rng = create_rng()

    step_a_and_b_clean_and_product_master()
    checkpoint()
    step_c_categories()
    step_d_cost_price(rng)
    step_e_suppliers(rng)
    step_f_stock_ledger()
    checkpoint()
    step_g_reorder()


if __name__ == "__main__":
    main()
