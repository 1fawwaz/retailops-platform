"""baseline

Revision ID: 5d2551341aaa
Revises:
Create Date: 2026-07-28 15:44:29.145643

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "5d2551341aaa"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
