"""add warehouses, location-scope stock_levels and stock_movements

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-08-01 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4a5b6c7d8e9"
down_revision: str | Sequence[str] | None = "e3f4a5b6c7d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MAIN_WAREHOUSE_NAME = "Main Warehouse"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "warehouses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Seed the one real location all pre-existing (single-location)
    # stock history is backfilled to -- not a fabricated split, an
    # explicit label for the one location the historical data already
    # represents. See docs/BUILD.md Backend Module 4.
    warehouses_table = sa.table(
        "warehouses", sa.column("id", sa.Integer()), sa.column("name", sa.String())
    )
    op.bulk_insert(warehouses_table, [{"name": MAIN_WAREHOUSE_NAME}])
    main_warehouse_id = (
        op.get_bind()
        .execute(
            sa.text("SELECT id FROM warehouses WHERE name = :name"), {"name": MAIN_WAREHOUSE_NAME}
        )
        .scalar_one()
    )

    # stock_levels: add nullable, backfill, then enforce NOT NULL
    op.add_column("stock_levels", sa.Column("warehouse_id", sa.Integer(), nullable=True))
    op.execute(
        sa.text("UPDATE stock_levels SET warehouse_id = :wid").bindparams(wid=main_warehouse_id)
    )
    op.alter_column("stock_levels", "warehouse_id", nullable=False)
    op.create_foreign_key(
        "fk_stock_levels_warehouse_id_warehouses",
        "stock_levels",
        "warehouses",
        ["warehouse_id"],
        ["id"],
    )
    op.drop_constraint("uq_stock_levels_sku_as_of_date", "stock_levels", type_="unique")
    op.create_unique_constraint(
        "uq_stock_levels_sku_warehouse_as_of_date",
        "stock_levels",
        ["sku", "warehouse_id", "as_of_date"],
    )

    # stock_movements: add nullable, backfill, then enforce NOT NULL
    op.add_column("stock_movements", sa.Column("warehouse_id", sa.Integer(), nullable=True))
    op.execute(
        sa.text("UPDATE stock_movements SET warehouse_id = :wid").bindparams(wid=main_warehouse_id)
    )
    op.alter_column("stock_movements", "warehouse_id", nullable=False)
    op.create_foreign_key(
        "fk_stock_movements_warehouse_id_warehouses",
        "stock_movements",
        "warehouses",
        ["warehouse_id"],
        ["id"],
    )
    op.drop_constraint("ck_stock_movements_movement_type", "stock_movements", type_="check")
    op.create_check_constraint(
        "ck_stock_movements_movement_type",
        "stock_movements",
        "movement_type IN ('sale', 'purchase_order', 'opening_balance', 'transfer', 'adjustment')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_stock_movements_movement_type", "stock_movements", type_="check")
    op.create_check_constraint(
        "ck_stock_movements_movement_type",
        "stock_movements",
        "movement_type IN ('sale', 'purchase_order', 'opening_balance')",
    )
    op.drop_constraint(
        "fk_stock_movements_warehouse_id_warehouses", "stock_movements", type_="foreignkey"
    )
    op.drop_column("stock_movements", "warehouse_id")

    op.drop_constraint("uq_stock_levels_sku_warehouse_as_of_date", "stock_levels", type_="unique")
    op.create_unique_constraint(
        "uq_stock_levels_sku_as_of_date", "stock_levels", ["sku", "as_of_date"]
    )
    op.drop_constraint(
        "fk_stock_levels_warehouse_id_warehouses", "stock_levels", type_="foreignkey"
    )
    op.drop_column("stock_levels", "warehouse_id")

    op.drop_table("warehouses")
