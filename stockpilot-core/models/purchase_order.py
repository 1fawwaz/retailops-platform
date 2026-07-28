from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class PurchaseOrder(Base):
    """Simulated purchase orders injected during the stock ledger replay
    wherever stock would otherwise go negative. Entirely derived -- this
    dataset has no real purchasing history. See
    data-derivation.md#stock-ledger.
    """

    __tablename__ = "purchase_orders"
    __table_args__ = (
        Index("ix_purchase_orders_sku", "sku"),
        Index("ix_purchase_orders_supplier_id", "supplier_id"),
        CheckConstraint(
            "status IN ('received')",
            name="ck_purchase_orders_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(ForeignKey("products.sku"))
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    order_date: Mapped[date] = mapped_column(
        Date,
        comment="derived: data-derivation.md#stock-ledger",
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        comment="derived: data-derivation.md#stock-ledger",
    )
    expected_arrival_date: Mapped[date] = mapped_column(
        Date,
        comment="derived: data-derivation.md#stock-ledger",
    )
    status: Mapped[str] = mapped_column(String)
