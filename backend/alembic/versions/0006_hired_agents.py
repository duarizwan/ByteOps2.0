"""Add hired_agents table
Revision ID: 0006
Revises: 0005_encrypt_tokens
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005_encrypt_tokens"
branch_labels = None
depends_on = None


def upgrade():
    # Drop and recreate enum with correct case — SQLAlchemy SAEnum sends the
    # Python enum .name (uppercase) not .value (lowercase).
    op.execute("DROP TYPE IF EXISTS hired_agent_status_enum CASCADE")
    op.execute(
        "CREATE TYPE hired_agent_status_enum AS ENUM ('ACTIVE', 'PAUSED', 'RUNNING', 'FAILED')"
    )

    op.create_table(
        "hired_agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("total_runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Cast status column to the enum type (must drop string default first)
    op.execute("ALTER TABLE hired_agents ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "ALTER TABLE hired_agents "
        "ALTER COLUMN status TYPE hired_agent_status_enum "
        "USING status::hired_agent_status_enum"
    )
    op.execute("ALTER TABLE hired_agents ALTER COLUMN status SET DEFAULT 'ACTIVE'::hired_agent_status_enum")

    op.create_index("ix_hired_agents_user_id", "hired_agents", ["user_id"])


def downgrade():
    op.drop_index("ix_hired_agents_user_id", "hired_agents")
    op.drop_table("hired_agents")
    op.execute("DROP TYPE IF EXISTS hired_agent_status_enum")
