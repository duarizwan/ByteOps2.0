"""add anomaly detection fields to agent_runs

Revision ID: 0003_anomaly_fields
Revises: 0002
Create Date: 2026-06-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_anomaly_fields"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("anomaly_score", sa.Float(), nullable=True))
    op.add_column("agent_runs", sa.Column("step_scores", JSONB(), nullable=True))
    op.add_column(
        "agent_runs",
        sa.Column("flagged", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "agent_runs",
        sa.Column("data_label", sa.String(length=20), nullable=False, server_default="unlabeled"),
    )


def downgrade() -> None:
    op.drop_column("agent_runs", "data_label")
    op.drop_column("agent_runs", "flagged")
    op.drop_column("agent_runs", "step_scores")
    op.drop_column("agent_runs", "anomaly_score")
