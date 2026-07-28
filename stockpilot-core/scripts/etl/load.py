"""Shared helpers for loading derived data into the database."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import Engine

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
