from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class AuditLog(Base):
    """Records who performed a permission-gated mutating action and
    when. Written at the point require_permission grants access, so it
    captures accepted actions with their user/permission/method/path --
    not a full before/after field diff (that would need per-resource
    hooks added everywhere; flagged as a larger undertaking, not built
    in this pass) and not denied attempts (a 403 never reaches this
    point). See docs/BUILD.md Backend Module 10.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_user_id_created_at", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    permission: Mapped[str] = mapped_column(String)
    method: Mapped[str] = mapped_column(String)
    path: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
