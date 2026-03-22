"""create core tables

Revision ID: 0001
Revises:
Create Date: 2026-03-21
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employees",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("skills_csv", sa.Text(), nullable=False, server_default=""),
        sa.Column("available", sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )

    op.create_table(
        "shifts",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("required_skill", sa.String(length=64), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "optimizer_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_shifts", sa.Integer(), nullable=False),
        sa.Column("unassigned_shifts", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
    )

    op.create_table(
        "assignment_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("optimizer_runs.id"), nullable=False),
        sa.Column("shift_id", sa.String(length=64), nullable=False),
        sa.Column("employee_id", sa.String(length=64), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False, server_default="proposed"),
    )


def downgrade() -> None:
    op.drop_table("assignment_events")
    op.drop_table("optimizer_runs")
    op.drop_table("shifts")
    op.drop_table("employees")
