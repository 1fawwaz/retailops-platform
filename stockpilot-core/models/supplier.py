from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Supplier(Base):
    """Suppliers. Seeded: 12-20 suppliers, one per SKU, with a
    deterministic lead time and reliability score.
    See data-derivation.md#supplier-assignment.
    """

    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        unique=True,
        comment="derived: data-derivation.md#supplier-assignment",
    )
    lead_time_days: Mapped[int] = mapped_column(
        Integer,
        comment="derived: data-derivation.md#supplier-assignment",
    )
    reliability_score: Mapped[float] = mapped_column(
        Float,
        comment="derived: data-derivation.md#supplier-assignment",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
