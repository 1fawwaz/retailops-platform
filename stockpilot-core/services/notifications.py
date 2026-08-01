from sqlalchemy import select
from sqlalchemy.orm import Session

from models.notification import Notification
from models.product import Product
from models.role import Role
from models.user_role import UserRole


def list_notifications(
    db: Session, user_id: int, *, unread_only: bool = False
) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc())
    return list(db.scalars(stmt))


def get_notification(db: Session, notification_id: int) -> Notification | None:
    return db.get(Notification, notification_id)


def mark_read(db: Session, notification: Notification, *, is_read: bool = True) -> Notification:
    notification.is_read = is_read
    db.commit()
    db.refresh(notification)
    return notification


def mark_all_read(db: Session, user_id: int) -> None:
    for notification in list_notifications(db, user_id, unread_only=True):
        notification.is_read = True
    db.commit()


def notify_users_with_permission(
    db: Session,
    *,
    permission: str,
    type: str,
    message: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> list[Notification]:
    """Fan out one Notification row per user who currently holds a role
    granting `permission` -- the people who can actually act on this
    event, per docs/PRODUCT-SPEC.md §16's trigger list. PRODUCT-SPEC
    doesn't name a specific recipient for each trigger, so "whoever can
    act on it" is the least-arbitrary interpretation available.
    """
    rows = db.execute(
        select(UserRole.user_id, Role.permissions).join(Role, Role.id == UserRole.role_id)
    )
    user_ids = {user_id for user_id, permissions in rows if permission in permissions}
    created = []
    for user_id in user_ids:
        notification = Notification(
            user_id=user_id,
            type=type,
            message=message,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        db.add(notification)
        created.append(notification)
    db.commit()
    for notification in created:
        db.refresh(notification)
    return created


def check_low_stock_crossing(
    db: Session, sku: str, old_quantity: int, new_quantity: int
) -> list[Notification]:
    """Fires only on the crossing itself (was above reorder_point, now
    at or below it) -- not on every subsequent change while already
    low, matching docs/PRODUCT-SPEC.md §16's "stock crosses below its
    reorder threshold" wording exactly.
    """
    reorder_point = db.scalar(select(Product.reorder_point).where(Product.sku == sku))
    if reorder_point is None:
        return []
    if old_quantity > reorder_point and new_quantity <= reorder_point:
        return notify_users_with_permission(
            db,
            permission="inventory:update",
            type="low_stock",
            message=f"'{sku}' has crossed its reorder point ({new_quantity} <= {reorder_point})",
            resource_type="product",
            resource_id=sku,
        )
    return []
