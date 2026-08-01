from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class UserRole(Base):
    """Many-to-many user<->role assignment. Many-to-many because
    docs/PRODUCT-SPEC.md §4 explicitly assumes a lean team where one
    person may hold more than one role. See docs/ARCHITECTURE.md §7.
    """

    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_id_role_id"),
        Index("ix_user_roles_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
