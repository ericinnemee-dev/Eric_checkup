"""add team and site scope columns

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-21
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("team_id", sa.String(length=64), nullable=True))
    op.add_column("employees", sa.Column("site_id", sa.String(length=64), nullable=True))
    op.add_column("shifts", sa.Column("team_id", sa.String(length=64), nullable=True))
    op.add_column("shifts", sa.Column("site_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("shifts", "site_id")
    op.drop_column("shifts", "team_id")
    op.drop_column("employees", "site_id")
    op.drop_column("employees", "team_id")
