from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.deps import require_permission
from database import get_db
from models.user import User
from schemas.audit_log import AuditLogRead
from services.audit_logs import list_audit_logs

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("", response_model=list[AuditLogRead])
def list_audit_logs_route(
    user_id: int | None = Query(default=None),
    permission: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("audit_logs:read")),
) -> list[AuditLogRead]:
    return [
        AuditLogRead.model_validate(entry)
        for entry in list_audit_logs(
            db,
            user_id=user_id,
            permission=permission,
            outcome=outcome,
            limit=limit,
            offset=offset,
        )
    ]
