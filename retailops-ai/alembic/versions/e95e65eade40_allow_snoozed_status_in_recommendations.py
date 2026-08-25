"""allow_snoozed_status_in_recommendations

Revision ID: e95e65eade40
Revises: 690cc23d7f69
Create Date: 2026-08-20 16:19:09.571991

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e95e65eade40"
down_revision: str | Sequence[str] | None = "690cc23d7f69"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("ck_recommendations_status", "recommendations", type_="check")
    op.create_check_constraint(
        "ck_recommendations_status",
        "recommendations",
        "status IN ('pending', 'accepted', 'rejected', 'snoozed')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_recommendations_status", "recommendations", type_="check")
    op.create_check_constraint(
        "ck_recommendations_status",
        "recommendations",
        "status IN ('pending', 'accepted', 'rejected')",
    )
