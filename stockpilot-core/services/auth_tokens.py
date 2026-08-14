from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.password_reset_token import PasswordResetToken
from models.refresh_token import RefreshToken
from models.user import User
from services.security import generate_opaque_token, hash_opaque_token
from settings import get_settings


def issue_refresh_token(db: Session, user: User) -> str:
    settings = get_settings()
    raw_token = generate_opaque_token()
    token = RefreshToken(
        user_id=user.id,
        token_hash=hash_opaque_token(raw_token),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(token)
    db.commit()
    return raw_token


def get_active_refresh_token(db: Session, raw_token: str) -> RefreshToken | None:
    token = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_opaque_token(raw_token))
    )
    if token is None or token.revoked_at is not None:
        return None
    if token.expires_at < datetime.now(UTC).replace(tzinfo=None):
        return None
    return token


def rotate_refresh_token(db: Session, raw_token: str) -> tuple[User, str] | None:
    """Single-use rotate on /refresh (SEC-02): validate the presented
    refresh token, revoke it, and issue a fresh one so a leaked token is
    worthless after its first use.

    Returns (user, new_raw_token) on success, or None if the token is
    unknown/expired/inactive -- the caller must not distinguish these
    cases in its response (docs/ARCHITECTURE.md §6).
    """
    token = get_active_refresh_token(db, raw_token)
    if token is None:
        return None
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        return None
    revoke_refresh_token(db, raw_token)
    new_raw_token = issue_refresh_token(db, user)
    return user, new_raw_token


def revoke_refresh_token(db: Session, raw_token: str) -> None:
    token = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_opaque_token(raw_token))
    )
    if token is None or token.revoked_at is not None:
        return
    token.revoked_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()


def revoke_all_refresh_tokens_for_user(db: Session, user_id: int) -> None:
    tokens = db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    for token in tokens:
        token.revoked_at = now
    db.commit()


def issue_password_reset_token(db: Session, user: User) -> str:
    settings = get_settings()
    raw_token = generate_opaque_token()
    token = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_opaque_token(raw_token),
        expires_at=datetime.now(UTC)
        + timedelta(minutes=settings.password_reset_token_expire_minutes),
    )
    db.add(token)
    db.commit()
    return raw_token


def consume_password_reset_token(db: Session, raw_token: str) -> User | None:
    """Validate and single-use-consume a password-reset token. Returns the
    matching user on success, or None if the token is unknown, already used,
    or expired -- the caller must not distinguish these cases in its response
    (see docs/ARCHITECTURE.md §6 on not confirming/denying account state).
    """
    token = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_opaque_token(raw_token)
        )
    )
    if token is None or token.used_at is not None:
        return None
    if token.expires_at < datetime.now(UTC).replace(tzinfo=None):
        return None
    token.used_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    return db.get(User, token.user_id)
