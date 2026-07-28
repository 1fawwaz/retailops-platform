from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class StockMovement(Base):
    """Append-only stock ledger entries: one row per event that changes
    a SKU's stock-on-hand. Sale-driven movements are observed; opening
    balances and injected purchase orders (added where the replay would
    otherwise go negative) are derived. See data-derivation.md#stock-ledger.
    """

    __tablename__ = "stock_movements"
    __table_args__ = (
        Index("ix_stock_movements_sku_movement_date", "sku", "movement_date"),
        CheckConstraint(
            "movement_type IN ('sale', 'purchase_order', 'opening_balance')",
            name="ck_stock_movements_movement_type",
        ),
        CheckConstraint(
            "provenance IN ('observed', 'derived')",
            name="ck_stock_movements_provenance",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(ForeignKey("products.sku"))
    movement_date: Mapped[datetime] = mapped_column(DateTime)
    quantity_delta: Mapped[int] = mapped_column(
        Integer,
        comment="derived: data-derivation.md#stock-ledger",
    )
    movement_type: Mapped[str] = mapped_column(String)
    reference: Mapped[str | None] = mapped_column(String)
    provenance: Mapped[str] = mapped_column(
        String,
        comment="derived: data-derivation.md#stock-ledger",
    )
