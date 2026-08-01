"""Mirrors stockpilot-frontend/lib/rbac/permissions.ts exactly -- that
file is the permission vocabulary spec (docs/ARCHITECTURE.md §7), not
something redesigned here. RESOURCES/ACTIONS and the helper functions
below are a direct Python transcription of ALL_RESOURCES/ALL_ACTIONS/
readOnly/fullAccess/everyAction; ROLE_PERMISSIONS is a direct
transcription of ROLE_PERMISSIONS.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.role import Role
from models.user_role import UserRole

RESOURCES = [
    "dashboard",
    "products",
    "inventory",
    "suppliers",
    "purchase_order",
    "sales",
    "customers",
    "forecasts",
    "analytics",
    "reports",
    "notifications",
    "audit_logs",
    "settings",
    "users",
    "roles",
    "profile",
]
ACTIONS = ["read", "create", "update", "delete", "receive"]


def _read_only(resources: list[str]) -> list[str]:
    return [f"{r}:read" for r in resources]


def _full_access(resources: list[str]) -> list[str]:
    return [f"{r}:{a}" for r in resources for a in ("read", "create", "update", "delete")]


def _every_action(resources: list[str]) -> list[str]:
    return [f"{r}:{a}" for r in resources for a in ACTIONS]


# Admin uses _every_action (not _full_access) deliberately -- "Everything,
# including Settings/Users/Roles" per docs/PRODUCT-SPEC.md §6 must include
# every action any other role has, including purchase_order's non-CRUD
# `receive` action (see the TS source's own comment about a caught bug
# here when it used fullAccess instead).
DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": _every_action(RESOURCES),
    "inventory_manager": [
        *_full_access(["inventory", "products", "suppliers"]),
        "purchase_order:read",
        "purchase_order:create",
        "purchase_order:receive",
        *_read_only(["analytics", "dashboard", "profile"]),
    ],
    "procurement": [
        *_full_access(["suppliers", "purchase_order"]),
        *_read_only(["inventory", "forecasts", "dashboard", "profile"]),
    ],
    "sales": [
        *_full_access(["sales", "customers"]),
        *_read_only(["products", "inventory", "dashboard", "profile"]),
    ],
    "analyst": _read_only(["dashboard", "analytics", "reports", "forecasts", "profile"]),
    "viewer": _read_only(["dashboard", "profile"]),
}


def seed_default_roles(db: Session) -> None:
    """Idempotent: only creates roles that don't already exist by name,
    so re-running against a DB with user-edited roles doesn't clobber
    them.
    """
    existing_names = set(db.scalars(select(Role.name)))
    for name, permissions in DEFAULT_ROLE_PERMISSIONS.items():
        if name not in existing_names:
            db.add(Role(name=name, permissions=permissions))
    db.commit()


def list_roles(db: Session) -> list[Role]:
    return list(db.scalars(select(Role).order_by(Role.name)))


def get_role(db: Session, role_id: int) -> Role | None:
    return db.get(Role, role_id)


def get_role_by_name(db: Session, name: str) -> Role | None:
    return db.scalar(select(Role).where(Role.name == name))


def create_role(db: Session, *, name: str, permissions: list[str]) -> Role:
    role = Role(name=name, permissions=permissions)
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def update_role_permissions(db: Session, role: Role, permissions: list[str]) -> Role:
    role.permissions = permissions
    db.commit()
    db.refresh(role)
    return role


def get_user_roles(db: Session, user_id: int) -> list[Role]:
    stmt = (
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
        .order_by(Role.name)
    )
    return list(db.scalars(stmt))


def get_resolved_permissions(db: Session, user_id: int) -> set[str]:
    """The union of every permission across every role assigned to this
    user -- supports multi-role per docs/PRODUCT-SPEC.md §4.
    """
    roles = get_user_roles(db, user_id)
    resolved: set[str] = set()
    for role in roles:
        resolved.update(role.permissions)
    return resolved


def assign_role(db: Session, user_id: int, role_id: int) -> UserRole | None:
    """Returns None (no-op) if the user already has this role, matching
    the idempotent-mutation discipline already used elsewhere (e.g.
    Backend Module 1's logout).
    """
    existing = db.scalar(
        select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
    )
    if existing is not None:
        return None
    assignment = UserRole(user_id=user_id, role_id=role_id)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def revoke_role(db: Session, user_id: int, role_id: int) -> None:
    assignment = db.scalar(
        select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
    )
    if assignment is not None:
        db.delete(assignment)
        db.commit()
