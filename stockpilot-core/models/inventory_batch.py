from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class InventoryBatch(Base):
    __tablename__ = "inventory_batches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_sku: Mapped[str | None] = mapped_column(ForeignKey("products.sku"))
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id"))
    batch_number: Mapped[str] = mapped_column(String(30), nullable=False)
    manufacturing_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    quantity_on_hand: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
