from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Payment(Base):
    """A recorded payment against an invoice. Recorded, not processed --
    no real payment-gateway integration exists (docs/BUILD.md Backend
    Module 7), matching the same discipline as Module 1's admin-mediated
    password reset: this is real data entry, not a half-real payment
    flow presented as automated.
    """

    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_invoice_id", "invoice_id"),
        CheckConstraint("amount > 0", name="ck_payments_amount"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    method: Mapped[str | None] = mapped_column(String)
    paid_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
