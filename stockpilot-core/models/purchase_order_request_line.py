from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class PurchaseOrderRequestLine(Base):
    """One SKU/quantity line on a purchase_order_requests header. See
    docs/BUILD.md Backend Module 5.
    """

    __tablename__ = "purchase_order_request_lines"
    __table_args__ = (
        Index("ix_purchase_order_request_lines_po_id", "purchase_order_request_id"),
        CheckConstraint("quantity_ordered > 0", name="ck_po_request_lines_quantity_ordered"),
        CheckConstraint("quantity_received >= 0", name="ck_po_request_lines_quantity_received"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    purchase_order_request_id: Mapped[int] = mapped_column(ForeignKey("purchase_order_requests.id"))
    sku: Mapped[str] = mapped_column(ForeignKey("products.sku"))
    quantity_ordered: Mapped[int] = mapped_column(Integer)
    quantity_received: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    unit_cost: Mapped[float | None] = mapped_column(Numeric(10, 2))
