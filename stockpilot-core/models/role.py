from datetime import datetime

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Role(Base):
    """A named set of "resource:action" permission strings. `name` and
    `permissions` mirror stockpilot-frontend's lib/rbac/permissions.ts
    exactly -- that file is the vocabulary spec this model implements,
    not something redesigned here. See docs/ARCHITECTURE.md §7.
    """

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    permissions: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
