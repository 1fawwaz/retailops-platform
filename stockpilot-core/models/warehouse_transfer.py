from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class WarehouseTransfer(Base):
    __tablename__ = "warehouse_transfers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_sku: Mapped[str | None] = mapped_column(ForeignKey("products.sku"))
    from_warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id"))
    to_warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id"))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    transfer_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str | None] = mapped_column(String(20))
