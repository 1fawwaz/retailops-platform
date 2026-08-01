from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Invoice(Base):
    """One invoice per sales_orders row, auto-generated when the order
    is confirmed. See docs/BUILD.md Backend Module 7.
    """

    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint(
            "status IN ('unpaid', 'partially_paid', 'paid')", name="ck_invoices_status"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sales_order_id: Mapped[int] = mapped_column(ForeignKey("sales_orders.id"), unique=True)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String, default="unpaid", server_default="unpaid")
    issued_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
