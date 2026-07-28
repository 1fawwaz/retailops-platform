from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class StockLevel(Base):
    """Daily stock-on-hand per SKU, materialized from replaying
    stock_movements chronologically. See data-derivation.md#stock-ledger.
    """

    __tablename__ = "stock_levels"
    __table_args__ = (
        UniqueConstraint("sku", "as_of_date", name="uq_stock_levels_sku_as_of_date"),
        Index("ix_stock_levels_sku_as_of_date", "sku", "as_of_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(ForeignKey("products.sku"))
    as_of_date: Mapped[date] = mapped_column(Date)
    quantity_on_hand: Mapped[int] = mapped_column(
        Integer,
        comment="derived: data-derivation.md#stock-ledger",
    )
