from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from services.rbac import get_resolved_permissions
from services.security import decode_access_token
from services.users import get_user_by_email

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        email = decode_access_token(token)
    except jwt.PyJWTError:
        raise credentials_error from None

    user = get_user_by_email(db, email)
    if user is None or not user.is_active:
        raise credentials_error
    return user


def require_permission(permission: str) -> Callable[[User, Session], User]:
    """Real server-side enforcement of the roles/permissions model
    (docs/ARCHITECTURE.md §7) -- every mutating endpoint uses this,
    not just the data structures a role's permissions live in. Folds
    in the existing is_read_only check as an additional hard override:
    ARCHITECTURE.md §7 explicitly decided not to remove is_read_only in
    this pass, so a read-only account is blocked from every non-read
    permission regardless of what its roles grant.
    """

    def _check(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if user.is_read_only and not permission.endswith(":read"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account is read-only",
            )
        resolved = get_resolved_permissions(db, user.id)
        if permission not in resolved:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {permission}",
            )
        return user

    return _check
