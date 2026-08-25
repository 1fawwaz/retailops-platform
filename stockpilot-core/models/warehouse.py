from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Warehouse(Base):
    """Stock locations. Seeded with one 'Main Warehouse' row that all
    pre-existing (single-location) stock_levels/stock_movements history
    is backfilled to -- see docs/BUILD.md Backend Module 4. Not a
    fabricated location split: it's an explicit label for the one real
    location the historical data already represents.
    """

    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(unique=True)
    location: Mapped[str | None] = mapped_column(String(160))
    state: Mapped[str | None] = mapped_column(String(40))
    zone: Mapped[str | None] = mapped_column(String(20))
    pin_code: Mapped[str | None] = mapped_column(String(6))
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    capacity_units: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
