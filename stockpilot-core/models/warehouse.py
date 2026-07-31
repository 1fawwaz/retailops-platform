from datetime import datetime

from sqlalchemy import DateTime, func
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
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
