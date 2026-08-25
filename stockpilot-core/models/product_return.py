from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ProductReturn(Base):
    __tablename__ = "returns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sale_id: Mapped[int | None] = mapped_column(ForeignKey("sales_transactions.id"))
    product_sku: Mapped[str | None] = mapped_column(ForeignKey("products.sku"))
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id"))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(30))
    return_date: Mapped[datetime | None] = mapped_column(DateTime)
    refund_amount_inr: Mapped[float | None] = mapped_column(Numeric(10, 2))
