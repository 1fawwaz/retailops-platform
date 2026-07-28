from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Product(Base):
    """Product master. sku and description are observed (distinct
    StockCode + Description from the source dataset). category_id,
    supplier_id, unit_cost, reorder_point, and safety_stock are all
    derived and backfilled by later ETL steps, so they start nullable.
    """

    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(primary_key=True)
    description: Mapped[str | None] = mapped_column()

    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"),
        comment="derived: data-derivation.md#category-clustering",
    )
    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id"),
        comment="derived: data-derivation.md#supplier-assignment",
    )
    unit_cost: Mapped[float | None] = mapped_column(
        Numeric(10, 2),
        comment="derived: data-derivation.md#cost-price",
    )
    reorder_point: Mapped[int | None] = mapped_column(
        Integer,
        comment="derived: data-derivation.md#reorder-point",
    )
    safety_stock: Mapped[int | None] = mapped_column(
        Integer,
        comment="derived: data-derivation.md#reorder-point",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
