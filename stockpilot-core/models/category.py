from datetime import datetime

from sqlalchemy import DateTime, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Category(Base):
    """Product categories. Derived by TF-IDF + KMeans clustering over
    product descriptions, then hand-labelled. See
    data-derivation.md#category-clustering.
    """

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        unique=True,
        comment="derived: data-derivation.md#category-clustering",
    )
    gst_percent: Mapped[float | None] = mapped_column(Numeric(4, 2))
    typical_margin_low: Mapped[float | None] = mapped_column(Numeric(5, 2))
    typical_margin_high: Mapped[float | None] = mapped_column(Numeric(5, 2))
    cost_range_low_inr: Mapped[float | None] = mapped_column(Numeric(10, 2))
    cost_range_high_inr: Mapped[float | None] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
