from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class InventoryAdjustment(Base):
    __tablename__ = "inventory_adjustments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_sku: Mapped[str | None] = mapped_column(ForeignKey("products.sku"))
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id"))
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_batches.id"))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(30))
    adjustment_date: Mapped[date | None] = mapped_column(Date)
