"""add shift route distance

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-21
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shifts",
        sa.Column("route_distance_km", sa.Float(), nullable=False, server_default=sa.text("0.0")),
    )


def downgrade() -> None:
    op.drop_column("shifts", "route_distance_km")
