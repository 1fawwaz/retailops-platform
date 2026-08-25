from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
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
    issue_password_reset_token,
    issue_refresh_token,
    revoke_all_refresh_tokens_for_user,
    revoke_refresh_token,
    rotate_refresh_token,
)
from services.rate_limit import rate_limited
from services.rbac import assign_role, get_resolved_permissions, get_role_by_name, get_user_roles
from services.security import create_access_token
from services.users import (
    authenticate_user,
    count_users,
    create_user,
    get_user_by_email,
    set_password,
)
from settings import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])

# SEC-01: the public, unauthenticated endpoints are rate-limited per
# client IP to blunt brute-force/password-stuffing. In-memory store --
# see services/rate_limit.py for the multi-worker caveat.
_login_limiter = rate_limited("auth:login", max_requests=30, window_seconds=300)
_register_limiter = rate_limited("auth:register", max_requests=10, window_seconds=3600)
_password_reset_request_limiter = rate_limited(
    "auth:password-reset-request", max_requests=10, window_seconds=3600
)
_password_reset_confirm_limiter = rate_limited(
    "auth:password-reset-confirm", max_requests=10, window_seconds=3600
)

# GET /me is deliberately a top-level route, not /auth/me
# (docs/ARCHITECTURE.md §6): it's the one call both a future profile page
# and the RBAC layer share.
me_router = APIRouter(tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(
    data: UserCreate,
    db: Session = Depends(get_db),
    _: None = Depends(_register_limiter),
) -> UserRead:
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


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:

    settings = get_settings()
    samesite_val = (
        settings.cookie_samesite if settings.cookie_samesite in ("lax", "strict", "none") else "lax"
    )
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=samesite_val,  # type: ignore[arg-type]
        domain=settings.cookie_domain,
        max_age=settings.jwt_access_token_expire_minutes * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=samesite_val,  # type: ignore[arg-type]
        domain=settings.cookie_domain,
        max_age=settings.refresh_token_expire_days * 86400,
    )


def _clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie("access_token", domain=settings.cookie_domain)
    response.delete_cookie("refresh_token", domain=settings.cookie_domain)


@router.post("/login", response_model=Token)
def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    _: None = Depends(_login_limiter),
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
    _set_auth_cookies(response, access_token, refresh_token)
    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    data: LogoutRequest | None = None,
    db: Session = Depends(get_db),
) -> Response:
    # Idempotent by design (docs/ARCHITECTURE.md §6): revoking an
    # already-revoked or unknown token still returns 204, never a
    # 404/409 a client has to special-case.
    token_str = (
        data.refresh_token
        if (data and data.refresh_token)
        else request.cookies.get("refresh_token")
    )
    if token_str:
        revoke_refresh_token(db, token_str)
    _clear_auth_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(
    request: Request,
    response: Response,
    data: RefreshRequest | None = None,
    db: Session = Depends(get_db),
) -> AccessTokenResponse:
    # SEC-02: refresh tokens are single-use and rotated. A replayed
    # (already-rotated) token revokes the user's whole session family.
    token_str = (
        data.refresh_token
        if (data and data.refresh_token)
        else request.cookies.get("refresh_token")
    )
    if not token_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    result = rotate_refresh_token(db, token_str)
    if result is None:
        _clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    user, new_refresh_token = result
    access_token = create_access_token(subject=user.email)
    _set_auth_cookies(response, access_token, new_refresh_token)
    return AccessTokenResponse(access_token=access_token, refresh_token=new_refresh_token)


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
def request_password_reset(
    data: PasswordResetRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_password_reset_request_limiter),
) -> Response:
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
def confirm_password_reset(
    data: PasswordResetConfirm,
    db: Session = Depends(get_db),
    _: None = Depends(_password_reset_confirm_limiter),
) -> Response:
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
