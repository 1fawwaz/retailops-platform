from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Brand(Base):
    """Product brands. User-entered catalog data, not derived from the
    source dataset (which has no brand field) -- see docs/BUILD.md
    Backend Module 2.
    """

    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
