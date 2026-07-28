"""Shared helpers for loading derived data into the database."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import Engine, update
from sqlalchemy.orm import Session

from models.category import Category
from models.product import Product
from models.supplier import Supplier

SALES_TRANSACTION_COLUMN_MAP = {
    "Invoice": "invoice",
    "StockCode": "sku",
    "Quantity": "quantity",
    "Price": "unit_price",
    "Customer ID": "customer_id",
    "Country": "country",
    "InvoiceDate": "invoice_date",
}


def insert_products(engine: Engine, product_df: pd.DataFrame) -> int:
    product_df[["sku", "description"]].to_sql(
        "products",
        engine,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=500,
    )
    return len(product_df)


def insert_sales_transactions(engine: Engine, cleaned_df: pd.DataFrame) -> int:
    to_load = cleaned_df.rename(columns=SALES_TRANSACTION_COLUMN_MAP)[
        list(SALES_TRANSACTION_COLUMN_MAP.values())
    ].copy()
    to_load["customer_id"] = to_load["customer_id"].astype("Int64")
    to_load.to_sql(
        "sales_transactions",
        engine,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=5000,
    )
    return len(to_load)


def insert_categories(session: Session, cluster_labels: dict[int, str]) -> dict[int, int]:
    """Insert one row per distinct label (in cluster_id order). Returns
    cluster_id -> categories.id.
    """
    cluster_to_category_id: dict[int, int] = {}
    for cluster_id in sorted(cluster_labels):
        category = Category(name=cluster_labels[cluster_id])
        session.add(category)
        session.flush()
        cluster_to_category_id[cluster_id] = category.id
    session.commit()
    return cluster_to_category_id


def update_product_categories(session: Session, sku_to_category_id: dict[str, int]) -> int:
    updates = [
        {"sku": sku, "category_id": category_id} for sku, category_id in sku_to_category_id.items()
    ]
    if not updates:
        return 0
    session.execute(update(Product), updates)
    session.commit()
    return len(updates)


def update_product_unit_costs(session: Session, sku_to_unit_cost: dict[str, float]) -> int:
    updates = [{"sku": sku, "unit_cost": unit_cost} for sku, unit_cost in sku_to_unit_cost.items()]
    if not updates:
        return 0
    session.execute(update(Product), updates)
    session.commit()
    return len(updates)


def insert_suppliers(session: Session, roster_df: pd.DataFrame) -> list[int]:
    """Inserts roster_df (columns: name, lead_time_days, reliability_score) in
    row order. Returns the resulting supplier ids in that same order, so index
    i in the roster maps to result[i].
    """
    supplier_ids: list[int] = []
    for name, lead_time_days, reliability_score in zip(
        roster_df["name"], roster_df["lead_time_days"], roster_df["reliability_score"], strict=True
    ):
        supplier = Supplier(
            name=str(name),
            lead_time_days=int(lead_time_days),
            reliability_score=float(reliability_score),
        )
        session.add(supplier)
        session.flush()
        supplier_ids.append(supplier.id)
    session.commit()
    return supplier_ids


def update_product_suppliers(session: Session, sku_to_supplier_id: dict[str, int]) -> int:
    updates = [
        {"sku": sku, "supplier_id": supplier_id} for sku, supplier_id in sku_to_supplier_id.items()
    ]
    if not updates:
        return 0
    session.execute(update(Product), updates)
    session.commit()
    return len(updates)


def insert_stock_movements(engine: Engine, rows: list[dict[str, object]]) -> int:
    if not rows:
        return 0
    pd.DataFrame(rows).to_sql(
        "stock_movements", engine, if_exists="append", index=False, method="multi", chunksize=5000
    )
    return len(rows)


def insert_stock_levels(engine: Engine, rows: list[dict[str, object]]) -> int:
    if not rows:
        return 0
    pd.DataFrame(rows).to_sql(
        "stock_levels", engine, if_exists="append", index=False, method="multi", chunksize=5000
    )
    return len(rows)


def insert_purchase_orders(engine: Engine, rows: list[dict[str, object]]) -> int:
    if not rows:
        return 0
    pd.DataFrame(rows).to_sql(
        "purchase_orders", engine, if_exists="append", index=False, method="multi", chunksize=5000
    )
    return len(rows)


def update_product_reorder_fields(session: Session, reorder_df: pd.DataFrame) -> int:
    """reorder_df needs columns sku, reorder_point, safety_stock."""
    updates = [
        {"sku": str(sku), "reorder_point": int(rp), "safety_stock": int(ss)}
        for sku, rp, ss in zip(
            reorder_df["sku"], reorder_df["reorder_point"], reorder_df["safety_stock"], strict=True
        )
    ]
    if not updates:
        return 0
    session.execute(update(Product), updates)
    session.commit()
    return len(updates)
