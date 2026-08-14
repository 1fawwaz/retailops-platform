from sqlalchemy import select
from sqlalchemy.orm import Session

from models.audit_log import AuditLog


def record_audit_log(
    db: Session, *, user_id: int, permission: str, method: str, path: str, outcome: str = "granted"
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id, permission=permission, method=method, path=path, outcome=outcome
    )
    db.add(entry)
    db.commit()
    return entry


def list_audit_logs(
    db: Session,
    *,
    user_id: int | None = None,
    permission: str | None = None,
    outcome: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if permission is not None:
        stmt = stmt.where(AuditLog.permission == permission)
    if outcome is not None:
        stmt = stmt.where(AuditLog.outcome == outcome)
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt))
