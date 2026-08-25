from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Supplier(Base):
    """Suppliers. Seeded: 12-20 suppliers, one per SKU, with a
    deterministic lead time and reliability score.
    See data-derivation.md#supplier-assignment.
    """

    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        unique=True,
        comment="derived: data-derivation.md#supplier-assignment",
    )
    lead_time_days: Mapped[int] = mapped_column(
        Integer,
        comment="derived: data-derivation.md#supplier-assignment",
    )
    reliability_score: Mapped[float] = mapped_column(
        Float,
        comment="derived: data-derivation.md#supplier-assignment",
    )
    city: Mapped[str | None] = mapped_column(String(60))
    state: Mapped[str | None] = mapped_column(String(40))
    pin_code: Mapped[str | None] = mapped_column(String(6))
    contact_person: Mapped[str | None] = mapped_column(String(100))
    mobile: Mapped[str | None] = mapped_column(String(15))
    contact_email: Mapped[str | None] = mapped_column(String(160))
    gstin: Mapped[str | None] = mapped_column(String(15))
    pan: Mapped[str | None] = mapped_column(String(10))
    udyam_number: Mapped[str | None] = mapped_column(String(20))
    fssai_license: Mapped[str | None] = mapped_column(String(20))
    avg_delay_days: Mapped[float | None] = mapped_column(Numeric(5, 2))
    on_time_percent: Mapped[float | None] = mapped_column(Numeric(5, 2))
    partial_shipment_percent: Mapped[float | None] = mapped_column(Numeric(5, 2))
    cancelled_percent: Mapped[float | None] = mapped_column(Numeric(5, 2))
    payment_terms: Mapped[str | None] = mapped_column(String(20))
    credit_days: Mapped[int | None] = mapped_column(Integer)
    moq: Mapped[int | None] = mapped_column(Integer)
    preferred_supplier: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
