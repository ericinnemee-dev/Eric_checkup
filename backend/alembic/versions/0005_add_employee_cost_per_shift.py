"""add employee cost_per_shift

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-21
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column("cost_per_shift", sa.Float(), nullable=False, server_default=sa.text("1.0")),
    )


def downgrade() -> None:
    op.drop_column("employees", "cost_per_shift")
