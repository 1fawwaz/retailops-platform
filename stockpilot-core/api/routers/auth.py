from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from api.deps import get_current_user
from database import get_db
from models.user import User
from schemas.me import MeRead
from schemas.user import (
    AccessTokenResponse,
    LogoutRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    Token,
    UserCreate,
    UserRead,
)
from services.auth_tokens import (
    consume_password_reset_token,
    get_active_refresh_token,
    issue_password_reset_token,
    issue_refresh_token,
    revoke_all_refresh_tokens_for_user,
    revoke_refresh_token,
)
from services.rbac import assign_role, get_resolved_permissions, get_role_by_name, get_user_roles
from services.security import create_access_token
from services.users import (
    authenticate_user,
    count_users,
    create_user,
    get_user_by_email,
    set_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# GET /me is deliberately a top-level route, not /auth/me
# (docs/ARCHITECTURE.md §6): it's the one call both a future profile page
# and the RBAC layer share.
me_router = APIRouter(tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    if get_user_by_email(db, data.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )
    # The very first account on a fresh deployment becomes admin --
    # otherwise nobody could ever assign the first role (user-confirmed
    # bootstrap decision, docs/BUILD.md Backend Module 10). Every
    # subsequent registration gets zero roles until an admin assigns one.
    is_first_user = count_users(db) == 0
    user = create_user(db, email=data.email, password=data.password)
    if is_first_user:
        admin_role = get_role_by_name(db, "admin")
        if admin_role is not None:
            assign_role(db, user.id, admin_role.id)
    return UserRead.model_validate(user)


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    user = authenticate_user(db, email=form_data.username, password=form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(subject=user.email)
    refresh_token = issue_refresh_token(db, user)
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(data: LogoutRequest, db: Session = Depends(get_db)) -> Response:
    # Idempotent by design (docs/ARCHITECTURE.md §6): revoking an
    # already-revoked or unknown token still returns 204, never a
    # 404/409 a client has to special-case.
    revoke_refresh_token(db, data.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)) -> AccessTokenResponse:
    token = get_active_refresh_token(db, data.refresh_token)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    access_token = create_access_token(subject=user.email)
    return AccessTokenResponse(access_token=access_token)


@me_router.get("/me", response_model=MeRead)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MeRead:
    roles = get_user_roles(db, user.id)
    permissions = get_resolved_permissions(db, user.id)
    return MeRead(
        user=UserRead.model_validate(user),
        roles=[r.name for r in roles],
        permissions=sorted(permissions),
    )


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(data: PasswordResetRequest, db: Session = Depends(get_db)) -> Response:
    # Always 202 regardless of whether the email matches a real account --
    # never confirm/deny account existence via response shape
    # (docs/ARCHITECTURE.md §6). No delivery channel exists yet (same
    # section's flagged open dependency): the token is generated and
    # stored so the flow is real end-to-end, but relaying it to the user
    # is admin/support-mediated for now, not emailed automatically.
    user = get_user_by_email(db, data.email)
    if user is not None:
        issue_password_reset_token(db, user)
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(data: PasswordResetConfirm, db: Session = Depends(get_db)) -> Response:
    user = consume_password_reset_token(db, data.token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    set_password(db, user, data.new_password)
    # A password reset ends every other session, deliberately
    # (docs/ARCHITECTURE.md §6).
    revoke_all_refresh_tokens_for_user(db, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
