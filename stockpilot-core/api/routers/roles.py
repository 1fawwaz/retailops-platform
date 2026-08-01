from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import require_permission
from database import get_db
from models.role import Role
from models.user import User
from schemas.role import RoleCreate, RoleRead, RoleUpdate
from services.rbac import (
    create_role,
    get_role,
    get_role_by_name,
    list_roles,
    update_role_permissions,
)

router = APIRouter(prefix="/roles", tags=["roles"])


def _get_role_or_404(db: Session, role_id: int) -> Role:
    role = get_role(db, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


@router.get("", response_model=list[RoleRead])
def list_roles_route(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("roles:read")),
) -> list[RoleRead]:
    return [RoleRead.model_validate(r) for r in list_roles(db)]


@router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
def create_role_route(
    data: RoleCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("roles:create")),
) -> RoleRead:
    if get_role_by_name(db, data.name) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Role '{data.name}' already exists"
        )
    return RoleRead.model_validate(create_role(db, name=data.name, permissions=data.permissions))


@router.put("/{role_id}", response_model=RoleRead)
def update_role_route(
    role_id: int,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("roles:update")),
) -> RoleRead:
    role = _get_role_or_404(db, role_id)
    return RoleRead.model_validate(update_role_permissions(db, role, data.permissions))
