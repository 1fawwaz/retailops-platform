"""add outcome to audit_logs

Revision ID: a1b2c3d4e5f6
Revises: f4a5b6c7d8e9
Create Date: 2026-08-14 00:00:00.000000

SEC-05: audit denied attempts too. Backfills existing rows as
"granted" (they were all recorded at grant time).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f4a5b6c7d8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("audit_logs", sa.Column("outcome", sa.String(), nullable=True))
    op.execute("UPDATE audit_logs SET outcome = 'granted' WHERE outcome IS NULL")
    op.alter_column("audit_logs", "outcome", existing_type=sa.String(), nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("audit_logs", "outcome")
