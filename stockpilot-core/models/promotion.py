from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Promotion(Base):
    __tablename__ = "promotions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    promo_type: Mapped[str] = mapped_column(String(30), nullable=False)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    discount_percent: Mapped[float | None] = mapped_column(Numeric(5, 2))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    budget_inr: Mapped[float | None] = mapped_column(Numeric(12, 2))
    redemption_count: Mapped[int | None] = mapped_column(Integer)
    sales_lift_percent: Mapped[float | None] = mapped_column(Numeric(6, 2))
    status: Mapped[str | None] = mapped_column(String(20))
