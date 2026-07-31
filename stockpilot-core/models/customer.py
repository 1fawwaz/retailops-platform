from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Customer(Base):
    """Real, live customer records entered through the app -- a fresh
    identity space, independent of the anonymized numeric
    sales_transactions.customer_id values in the historical dataset
    (which have no name/contact info to attach a real Customer record
    to). See docs/BUILD.md Backend Module 6.
    """

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    phone: Mapped[str | None] = mapped_column(String)
    country: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
