"""add_cloudinary_image_urls

Revision ID: f7a8b9c0d1e2
Revises: c80c9cae5095
Create Date: 2026-08-20 16:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: str | Sequence[str] | None = "c80c9cae5095"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("products", sa.Column("image_url", sa.String(length=500), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("products", "image_url")
    op.drop_column("users", "avatar_url")
