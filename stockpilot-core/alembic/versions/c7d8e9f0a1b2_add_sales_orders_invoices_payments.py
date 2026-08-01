"""add sales_orders, sales_order_lines, invoices, payments

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
Create Date: 2026-08-01 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d8e9f0a1b2"
down_revision: str | Sequence[str] | None = "b6c7d8e9f0a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "sales_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), server_default="draft", nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'confirmed', 'fulfilled', 'cancelled')",
            name="ck_sales_orders_status",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_sales_orders_customer_id"), "sales_orders", ["customer_id"], unique=False
    )
    op.create_index(op.f("ix_sales_orders_status"), "sales_orders", ["status"], unique=False)

    op.create_table(
        "sales_order_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sales_order_id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_sales_order_lines_quantity"),
        sa.ForeignKeyConstraint(["sales_order_id"], ["sales_orders.id"]),
        sa.ForeignKeyConstraint(["sku"], ["products.sku"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_sales_order_lines_order_id"), "sales_order_lines", ["sales_order_id"], unique=False
    )

    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sales_order_id", sa.Integer(), nullable=False),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(), server_default="unpaid", nullable=False),
        sa.Column("issued_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('unpaid', 'partially_paid', 'paid')", name="ck_invoices_status"
        ),
        sa.ForeignKeyConstraint(["sales_order_id"], ["sales_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sales_order_id"),
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("invoice_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("method", sa.String(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_payments_amount"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_payments_invoice_id"), "payments", ["invoice_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_payments_invoice_id"), table_name="payments")
    op.drop_table("payments")

    op.drop_table("invoices")

    op.drop_index(op.f("ix_sales_order_lines_order_id"), table_name="sales_order_lines")
    op.drop_table("sales_order_lines")

    op.drop_index(op.f("ix_sales_orders_status"), table_name="sales_orders")
    op.drop_index(op.f("ix_sales_orders_customer_id"), table_name="sales_orders")
    op.drop_table("sales_orders")
