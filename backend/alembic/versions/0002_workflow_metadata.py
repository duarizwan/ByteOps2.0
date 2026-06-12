"""Add workflow metadata column

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-31
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "workflows",
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
    )


def downgrade():
    op.drop_column("workflows", "metadata")
