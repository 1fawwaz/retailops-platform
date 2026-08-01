from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import require_permission
from database import get_db
from models.user import User
from schemas.user import UserWithRolesRead
from services.rbac import assign_role, get_role, get_user_roles, revoke_role
from services.users import get_user, list_users

router = APIRouter(prefix="/users", tags=["users"])


def _to_read_model(user: User, db: Session) -> UserWithRolesRead:
    roles = get_user_roles(db, user.id)
    return UserWithRolesRead(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_read_only=user.is_read_only,
        created_at=user.created_at,
        roles=[r.name for r in roles],
    )


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("", response_model=list[UserWithRolesRead])
def list_users_route(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("users:read")),
) -> list[UserWithRolesRead]:
    return [_to_read_model(u, db) for u in list_users(db)]


@router.get("/{user_id}", response_model=UserWithRolesRead)
def get_user_route(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("users:read")),
) -> UserWithRolesRead:
    return _to_read_model(_get_user_or_404(db, user_id), db)


@router.post(
    "/{user_id}/roles/{role_id}",
    response_model=UserWithRolesRead,
    status_code=status.HTTP_201_CREATED,
)
def assign_role_route(
    user_id: int,
    role_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("users:update")),
) -> UserWithRolesRead:
    target_user = _get_user_or_404(db, user_id)
    if get_role(db, role_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    assign_role(db, user_id, role_id)
    return _to_read_model(target_user, db)


@router.delete(
    "/{user_id}/roles/{role_id}",
    response_model=UserWithRolesRead,
)
def revoke_role_route(
    user_id: int,
    role_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("users:update")),
) -> UserWithRolesRead:
    target_user = _get_user_or_404(db, user_id)
    if get_role(db, role_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    revoke_role(db, user_id, role_id)
    return _to_read_model(target_user, db)
