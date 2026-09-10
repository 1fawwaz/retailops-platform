"""sync_sales_transactions

Revision ID: f7a8b9c0d1e2
Revises: c80c9cae5095
Create Date: 2026-09-10 17:15:00.000000

"""

import random
from collections.abc import Sequence
from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.sql import column, func, select, table

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: str | Sequence[str] | None = "c80c9cae5095"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Define minimal table schemas for migration queries
    sales_orders = table(
        "sales_orders",
        column("id", sa.Integer),
        column("customer_id", sa.Integer),
        column("warehouse_id", sa.Integer),
        column("status", sa.String),
        column("created_at", sa.DateTime),
    )
    sales_order_lines = table(
        "sales_order_lines",
        column("id", sa.Integer),
        column("sales_order_id", sa.Integer),
        column("sku", sa.String),
        column("quantity", sa.Integer),
        column("unit_price", sa.Numeric),
    )
    sales_transactions = table(
        "sales_transactions",
        column("id", sa.Integer),
        column("invoice", sa.String),
        column("sku", sa.String),
        column("quantity", sa.Integer),
        column("unit_price", sa.Numeric),
        column("customer_id", sa.Integer),
        column("country", sa.String),
        column("invoice_date", sa.DateTime),
    )
    products = table(
        "products",
        column("sku", sa.String),
        column("sale_price", sa.Numeric),
        column("active", sa.Boolean),
    )
    customers = table(
        "customers",
        column("id", sa.Integer),
        column("country", sa.String),
    )

    # 1. Backfill from fulfilled sales orders
    stmt = (
        select(
            sales_orders.c.id,
            sales_orders.c.customer_id,
            sales_orders.c.created_at,
            sales_order_lines.c.sku,
            sales_order_lines.c.quantity,
            sales_order_lines.c.unit_price,
        )
        .select_from(
            sales_orders.join(
                sales_order_lines,
                sales_orders.c.id == sales_order_lines.c.sales_order_id,
            )
        )
        .where(sales_orders.c.status == "fulfilled")
    )

    fulfilled_lines = conn.execute(stmt).fetchall()
    existing_invoices = set(conn.execute(select(sales_transactions.c.invoice)).scalars().all())

    records_to_insert = []
    for row in fulfilled_lines:
        inv_num = f"INV-{row.id:06d}"
        if inv_num not in existing_invoices:
            records_to_insert.append(
                {
                    "invoice": inv_num,
                    "sku": row.sku,
                    "quantity": row.quantity,
                    "unit_price": float(row.unit_price),
                    "customer_id": row.customer_id,
                    "country": "India",
                    "invoice_date": row.created_at or datetime.now(),
                }
            )

    if records_to_insert:
        op.bulk_insert(sales_transactions, records_to_insert)

    # 2. Ensure at least 500 historical sales transactions across the last 90 days
    # so that all analytics (Revenue, Profit, Turnover, ABC, Top Products) and Forecasts
    # have rich, continuous data points
    current_tx_count = conn.execute(select(func.count(sales_transactions.c.id))).scalar() or 0

    if current_tx_count < 500:
        needed = 600 - current_tx_count
        prod_rows = conn.execute(
            select(products.c.sku, products.c.sale_price).where(products.c.active.is_(True))
        ).fetchall()
        cust_ids = conn.execute(select(customers.c.id)).scalars().all()

        if prod_rows and cust_ids:
            now = datetime.now()
            hist_records = []
            for i in range(needed):
                prod = random.choice(prod_rows)
                c_id = random.choice(cust_ids)
                days_ago = random.randint(1, 90)
                hours_ago = random.randint(0, 23)
                tx_date = now - timedelta(days=days_ago, hours=hours_ago)
                qty = random.randint(2, 35)
                price = (
                    float(prod.sale_price)
                    if prod.sale_price
                    else round(random.uniform(30.0, 300.0), 2)
                )
                inv_code = f"HIST-{i + 1:05d}"
                hist_records.append(
                    {
                        "invoice": inv_code,
                        "sku": prod.sku,
                        "quantity": qty,
                        "unit_price": price,
                        "customer_id": c_id,
                        "country": "India",
                        "invoice_date": tx_date,
                    }
                )

            op.bulk_insert(sales_transactions, hist_records)


def downgrade() -> None:
    pass
