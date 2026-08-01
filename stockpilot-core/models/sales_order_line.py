from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class SalesOrderLine(Base):
    """One SKU/quantity line on a sales_orders header. See
    docs/BUILD.md Backend Module 7.
    """

    __tablename__ = "sales_order_lines"
    __table_args__ = (
        Index("ix_sales_order_lines_order_id", "sales_order_id"),
        CheckConstraint("quantity > 0", name="ck_sales_order_lines_quantity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sales_order_id: Mapped[int] = mapped_column(ForeignKey("sales_orders.id"))
    sku: Mapped[str] = mapped_column(ForeignKey("products.sku"))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2))
