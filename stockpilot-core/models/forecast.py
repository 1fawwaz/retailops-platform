from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Forecast(Base):
    __tablename__ = "forecasts"

    product_sku: Mapped[str] = mapped_column(ForeignKey("products.sku"), primary_key=True)
    forecast_date: Mapped[date] = mapped_column(Date, primary_key=True)
    horizon_days: Mapped[int] = mapped_column(Integer, primary_key=True)
    predicted_demand: Mapped[float | None] = mapped_column(Numeric(10, 2))
    recommended_reorder_qty: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 2))
