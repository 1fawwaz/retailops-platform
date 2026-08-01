"""add audit_logs, notifications, settings

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-08-01 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e9f0a1b2c3d4"
down_revision: str | Sequence[str] | None = "d8e9f0a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(), nullable=False),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_audit_logs_user_id_created_at"),
        "audit_logs",
        ["user_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=True),
        sa.Column("resource_id", sa.String(), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notifications_user_id_is_read"),
        "notifications",
        ["user_id", "is_read"],
        unique=False,
    )

    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("currency", sa.String(), server_default="GBP", nullable=False),
        sa.Column("timezone", sa.String(), server_default="Europe/London", nullable=False),
        sa.Column(
            "low_stock_notifications_enabled", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # Singleton row -- created here rather than lazily on first request,
    # so GET /settings always has a real row from the moment this
    # migration runs.
    settings_table = sa.table(
        "settings",
        sa.column("currency", sa.String()),
        sa.column("timezone", sa.String()),
        sa.column("low_stock_notifications_enabled", sa.Boolean()),
    )
    op.bulk_insert(
        settings_table,
        [
            {
                "currency": "GBP",
                "timezone": "Europe/London",
                "low_stock_notifications_enabled": True,
            }
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("settings")

    op.drop_index(op.f("ix_notifications_user_id_is_read"), table_name="notifications")
    op.drop_table("notifications")

    op.drop_index(op.f("ix_audit_logs_user_id_created_at"), table_name="audit_logs")
    op.drop_table("audit_logs")
