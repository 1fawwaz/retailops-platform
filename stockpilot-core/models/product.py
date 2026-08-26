from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
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

    barcode: Mapped[str | None] = mapped_column(String(13), unique=True)
    name: Mapped[str | None] = mapped_column(String(160))
    gst_percent: Mapped[float | None] = mapped_column(Numeric(4, 2))
    hsn_code: Mapped[str | None] = mapped_column(String(8))
    shelf_life_days: Mapped[int | None] = mapped_column(Integer)
    weight_grams: Mapped[float | None] = mapped_column(Numeric(10, 2))
    reorder_quantity: Mapped[int | None] = mapped_column(Integer)
    eoq: Mapped[int | None] = mapped_column(Integer)
    abc_class: Mapped[str | None] = mapped_column(String(1))
    xyz_class: Mapped[str | None] = mapped_column(String(1))
    behavior_pattern: Mapped[str | None] = mapped_column(String(20))
    active: Mapped[bool | None] = mapped_column(Boolean)

    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"),
        comment="derived: data-derivation.md#category-clustering",
    )
    supplier_id: Mapped[int | None] = mapped_column(
        ForeignKey("suppliers.id"),
        comment="derived: data-derivation.md#supplier-assignment",
    )
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("brands.id"))
    unit_cost: Mapped[float | None] = mapped_column(
        Numeric(10, 2),
        comment="derived: data-derivation.md#cost-price",
    )
    sale_price: Mapped[float | None] = mapped_column(
        Numeric(10, 2),
        comment="derived: backfilled from the SKU's average observed "
        "sales_transactions.unit_price (docs/BUILD.md Backend Module 2); "
        "user-editable going forward via PUT /products/{sku}",
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
