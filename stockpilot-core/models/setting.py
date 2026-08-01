from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Setting(Base):
    """Tenant-level settings -- a singleton row (this is a single-tenant
    app, per everything else built so far). See docs/BUILD.md Backend
    Module 10. Currency defaults to GBP: this is a UK dataset end to end
    (CLAUDE.md), not an arbitrary default.
    """

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    currency: Mapped[str] = mapped_column(String, default="GBP", server_default="GBP")
    timezone: Mapped[str] = mapped_column(
        String, default="Europe/London", server_default="Europe/London"
    )
    low_stock_notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
