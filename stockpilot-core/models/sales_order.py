from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class SalesOrder(Base):
    """The real, live Sales Order workflow entity -- entirely separate
    from (and never merged with) the historical sales_transactions
    table, per the user's explicit decision when this module was
    built (docs/BUILD.md Backend Module 7, docs/stockpilot-gaps.md #6).
    Orders placed through the app from here forward; sales_transactions
    stays the permanent historical record analytics continues to read.
    """

    __tablename__ = "sales_orders"
    __table_args__ = (
        Index("ix_sales_orders_customer_id", "customer_id"),
        Index("ix_sales_orders_status", "status"),
        CheckConstraint(
            "status IN ('draft', 'confirmed', 'fulfilled', 'cancelled')",
            name="ck_sales_orders_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    status: Mapped[str] = mapped_column(String, default="draft", server_default="draft")
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
