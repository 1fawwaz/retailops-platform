"""add roles and user_roles, seed the six default roles

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-08-01 00:00:00.000000

"""

import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8e9f0a1b2c3"
down_revision: str | Sequence[str] | None = "c7d8e9f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Duplicated (not imported) from services/rbac.py deliberately: a
# migration's data must stay exactly what it was the day it ran, even
# if the application's permission vocabulary changes later. This is a
# direct transcription of stockpilot-frontend's lib/rbac/permissions.ts
# (docs/ARCHITECTURE.md §7), same as services/rbac.py.
_RESOURCES = [
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
_ACTIONS = ["read", "create", "update", "delete", "receive"]


def _read_only(resources: list[str]) -> list[str]:
    return [f"{r}:read" for r in resources]


def _full_access(resources: list[str]) -> list[str]:
    return [f"{r}:{a}" for r in resources for a in ("read", "create", "update", "delete")]


def _every_action(resources: list[str]) -> list[str]:
    return [f"{r}:{a}" for r in resources for a in _ACTIONS]


_DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": _every_action(_RESOURCES),
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


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_id_role_id"),
    )
    op.create_index(op.f("ix_user_roles_user_id"), "user_roles", ["user_id"], unique=False)

    # Use explicit JSON literals instead of ``op.bulk_insert``. Alembic's
    # offline renderer cannot render Python lists for a generic JSON column,
    # while these static JSON literals work for both PostgreSQL execution and
    # ``alembic upgrade --sql`` output.
    for name, permissions in _DEFAULT_ROLE_PERMISSIONS.items():
        permissions_json = json.dumps(permissions).replace("'", "''")
        op.execute(
            f"INSERT INTO roles (name, permissions) VALUES ('{name}', '{permissions_json}'::json)"
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_user_roles_user_id"), table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_table("roles")
