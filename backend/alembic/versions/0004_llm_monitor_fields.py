"""add llm monitor fields to agent_runs

Revision ID: 0004_llm_monitor_fields
Revises: 0003_anomaly_fields
Create Date: 2026-06-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_llm_monitor_fields"
down_revision = "0003_anomaly_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("llm_score", sa.Integer(), nullable=True))
    op.add_column("agent_runs", sa.Column("llm_reasoning", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_runs", "llm_reasoning")
    op.drop_column("agent_runs", "llm_score")
