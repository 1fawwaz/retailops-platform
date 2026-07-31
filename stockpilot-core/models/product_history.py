from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ProductHistory(Base):
    """Append-only audit trail of field-level changes to a product.
    One row per changed field per update -- see docs/BUILD.md Backend
    Module 2. Not business data itself, so no provenance labelling.
    """

    __tablename__ = "product_history"
    __table_args__ = (Index("ix_product_history_sku_changed_at", "sku", "changed_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(ForeignKey("products.sku"))
    field_name: Mapped[str] = mapped_column(String)
    old_value: Mapped[str | None] = mapped_column(String)
    new_value: Mapped[str | None] = mapped_column(String)
    changed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
