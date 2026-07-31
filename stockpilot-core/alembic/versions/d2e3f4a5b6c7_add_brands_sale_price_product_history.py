"""add brands, product sale_price/brand_id, product_history

Revision ID: d2e3f4a5b6c7
Revises: c1a2b3d4e5f6
Create Date: 2026-08-01 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2e3f4a5b6c7"
down_revision: str | Sequence[str] | None = "c1a2b3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "brands",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.add_column("products", sa.Column("brand_id", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("sale_price", sa.Numeric(10, 2), nullable=True))
    op.create_foreign_key("fk_products_brand_id_brands", "products", "brands", ["brand_id"], ["id"])

    # Backfill: sale_price = the SKU's average observed sales_transactions
    # unit_price, per the sourcing decision in docs/BUILD.md Backend Module
    # 2 / docs/stockpilot-gaps.md #2. Products with no sales history keep
    # sale_price NULL rather than a fabricated default.
    op.execute(
        "UPDATE products SET sale_price = ("
        "SELECT AVG(unit_price) FROM sales_transactions "
        "WHERE sales_transactions.sku = products.sku"
        ")"
    )

    op.create_table(
        "product_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sku", sa.String(), nullable=False),
        sa.Column("field_name", sa.String(), nullable=False),
        sa.Column("old_value", sa.String(), nullable=True),
        sa.Column("new_value", sa.String(), nullable=True),
        sa.Column("changed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("changed_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["sku"], ["products.sku"]),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_product_history_sku_changed_at"),
        "product_history",
        ["sku", "changed_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_product_history_sku_changed_at"), table_name="product_history")
    op.drop_table("product_history")

    op.drop_constraint("fk_products_brand_id_brands", "products", type_="foreignkey")
    op.drop_column("products", "sale_price")
    op.drop_column("products", "brand_id")

    op.drop_table("brands")
