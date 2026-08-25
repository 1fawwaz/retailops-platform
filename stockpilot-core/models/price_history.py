from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_sku: Mapped[str | None] = mapped_column(ForeignKey("products.sku"))
    old_price_inr: Mapped[float | None] = mapped_column(Numeric(10, 2))
    new_price_inr: Mapped[float | None] = mapped_column(Numeric(10, 2))
    effective_date: Mapped[date | None] = mapped_column(Date)
    reason: Mapped[str | None] = mapped_column(String(30))
