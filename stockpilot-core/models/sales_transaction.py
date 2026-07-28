from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class SalesTransaction(Base):
    """Cleaned sales line items (cancellations, non-positive quantities,
    and null StockCodes already dropped by ETL). Every column here is
    observed, straight from the source dataset.
    """

    __tablename__ = "sales_transactions"
    __table_args__ = (Index("ix_sales_transactions_sku_invoice_date", "sku", "invoice_date"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    invoice: Mapped[str] = mapped_column(String, index=True)
    sku: Mapped[str] = mapped_column(ForeignKey("products.sku"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2))
    customer_id: Mapped[int | None] = mapped_column(Integer)
    country: Mapped[str] = mapped_column(String)
    invoice_date: Mapped[datetime] = mapped_column(DateTime, index=True)
