"""Add hired_agent_id FK to agent_runs
Revision ID: 0007
Revises: 0006
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "agent_runs",
        sa.Column(
            "hired_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hired_agents.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_agent_runs_hired_agent_id",
        "agent_runs",
        ["hired_agent_id"],
    )


def downgrade():
    op.drop_index("ix_agent_runs_hired_agent_id", table_name="agent_runs")
    op.drop_column("agent_runs", "hired_agent_id")
