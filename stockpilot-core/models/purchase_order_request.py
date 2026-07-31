from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base

OPEN_STATUSES = ("draft", "submitted", "approved", "partially_received")
"""Statuses that count as "open" for the supplier/product deletion
guards in PRODUCT-SPEC.md §12 -- 'received' is fully delivered but not
yet formally closed out, so it's deliberately excluded (nothing left to
happen against the supplier/product from a still-open PO)."""


class PurchaseOrderRequest(Base):
    """The real, live Purchase Order workflow entity -- named
    purchase_order_requests (not purchase_orders) to avoid colliding
    with the pre-existing purchase_orders table, which is synthetic
    data injected during stock-ledger replay and has no real lifecycle
    (docs/stockpilot-gaps.md #6). That table is untouched by this
    module. See docs/PRODUCT-SPEC.md §10/§12 for the lifecycle this
    model implements.
    """

    __tablename__ = "purchase_order_requests"
    __table_args__ = (
        Index("ix_purchase_order_requests_supplier_id", "supplier_id"),
        Index("ix_purchase_order_requests_status", "status"),
        CheckConstraint(
            "status IN ('draft', 'submitted', 'approved', 'partially_received', "
            "'received', 'closed', 'cancelled')",
            name="ck_purchase_order_requests_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"))
    status: Mapped[str] = mapped_column(String, default="draft", server_default="draft")
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
