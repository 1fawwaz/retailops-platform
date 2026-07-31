from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class SupplierContact(Base):
    """A named point of contact at a supplier. User-entered catalog data,
    not derived from the source dataset -- see docs/BUILD.md Backend
    Module 3.
    """

    __tablename__ = "supplier_contacts"
    __table_args__ = (Index("ix_supplier_contacts_supplier_id", "supplier_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    phone: Mapped[str | None] = mapped_column(String)
    role: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
