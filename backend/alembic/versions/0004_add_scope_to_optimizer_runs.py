"""add team/site scope to optimizer runs

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-21
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("optimizer_runs", sa.Column("team_id", sa.String(length=64), nullable=True))
    op.add_column("optimizer_runs", sa.Column("site_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("optimizer_runs", "site_id")
    op.drop_column("optimizer_runs", "team_id")
