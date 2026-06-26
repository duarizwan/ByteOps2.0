"""widen token columns to TEXT for encryption-at-rest

Revision ID: 0005_encrypt_tokens
Revises: 0004_llm_monitor_fields
Create Date: 2026-06-13

Encrypted (Fernet) tokens are longer than the plaintext, so the fixed
VARCHAR(4096) columns are widened to TEXT. No data is transformed here;
existing plaintext rows remain readable and are encrypted lazily on next write
(see app/core/crypto.EncryptedString).
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_encrypt_tokens"
down_revision = "0004_llm_monitor_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("tool_connections", "access_token",
                    type_=sa.Text(), existing_type=sa.String(4096), existing_nullable=False)
    op.alter_column("tool_connections", "refresh_token",
                    type_=sa.Text(), existing_type=sa.String(4096), existing_nullable=True)


def downgrade() -> None:
    op.alter_column("tool_connections", "access_token",
                    type_=sa.String(4096), existing_type=sa.Text(), existing_nullable=False)
    op.alter_column("tool_connections", "refresh_token",
                    type_=sa.String(4096), existing_type=sa.Text(), existing_nullable=True)
