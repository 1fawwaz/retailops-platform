from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from api.deps import get_current_user
from database import get_db
from models.notification import Notification
from models.user import User
from schemas.notification import NotificationMarkRead, NotificationRead
from services.notifications import (
    get_notification,
    list_notifications,
    mark_all_read,
    mark_read,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _get_own_notification_or_404(db: Session, notification_id: int, user_id: int) -> Notification:
    notification = get_notification(db, notification_id)
    if notification is None or notification.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return notification


@router.get("", response_model=list[NotificationRead])
def list_notifications_route(
    unread_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[NotificationRead]:
    return [
        NotificationRead.model_validate(n)
        for n in list_notifications(db, user.id, unread_only=unread_only)
    ]


@router.patch("/{notification_id}", response_model=NotificationRead)
def mark_notification_read_route(
    notification_id: int,
    data: NotificationMarkRead,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NotificationRead:
    notification = _get_own_notification_or_404(db, notification_id, user.id)
    return NotificationRead.model_validate(mark_read(db, notification, is_read=data.is_read))


@router.post("/mark-all-read", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_notifications_read_route(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    mark_all_read(db, user.id)
