"""baseline

Revision ID: 5e150b7ad8b2
Revises:
Create Date: 2026-07-28 15:44:15.057978

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "5e150b7ad8b2"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
