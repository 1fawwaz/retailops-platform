"""add purchase_order_requests and purchase_order_request_lines

Revision ID: a5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-08-01 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a5b6c7d8e9f0"
down_revision: str | Sequence[str] | None = "f4a5b6c7d8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "purchase_order_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), server_default="draft", nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted', 'approved', 'partially_received', "
            "'received', 'closed', 'cancelled')",
            name="ck_purchase_order_requests_status",
        ),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_purchase_order_requests_supplier_id"),
        "purchase_order_requests",
        ["supplier_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_purchase_order_requests_status"),
        "purchase_order_requests",
        ["status"],
        unique=False,
    )

    op.create_table(
        "purchase_order_request_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("purchase_order_request_id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(), nullable=False),
        sa.Column("quantity_ordered", sa.Integer(), nullable=False),
        sa.Column("quantity_received", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unit_cost", sa.Numeric(10, 2), nullable=True),
        sa.CheckConstraint("quantity_ordered > 0", name="ck_po_request_lines_quantity_ordered"),
        sa.CheckConstraint("quantity_received >= 0", name="ck_po_request_lines_quantity_received"),
        sa.ForeignKeyConstraint(["purchase_order_request_id"], ["purchase_order_requests.id"]),
        sa.ForeignKeyConstraint(["sku"], ["products.sku"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_purchase_order_request_lines_po_id"),
        "purchase_order_request_lines",
        ["purchase_order_request_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_purchase_order_request_lines_po_id"),
        table_name="purchase_order_request_lines",
    )
    op.drop_table("purchase_order_request_lines")

    op.drop_index(op.f("ix_purchase_order_requests_status"), table_name="purchase_order_requests")
    op.drop_index(
        op.f("ix_purchase_order_requests_supplier_id"), table_name="purchase_order_requests"
    )
    op.drop_table("purchase_order_requests")
