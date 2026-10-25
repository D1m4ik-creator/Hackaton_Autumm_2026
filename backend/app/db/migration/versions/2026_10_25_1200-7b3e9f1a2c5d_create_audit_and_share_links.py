"""create audit and share links

Revision ID: 7b3e9f1a2c5d
Revises: c44b769d2fba
Create Date: 2026-10-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "7b3e9f1a2c5d"
down_revision: Union[str, Sequence[str], None] = "c44b769d2fba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "model_settings_audit",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("actor_login", sa.Text(), nullable=False),
        sa.Column("actor_role", sa.Text(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("section", sa.Text(), nullable=True),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_model_settings_audit_user_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_settings_audit")),
    )
    op.create_index(op.f("ix_model_settings_audit_created_at"), "model_settings_audit", ["created_at"], unique=False)

    op.create_table(
        "share_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("created_by_login", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_share_links")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_share_links_token_hash")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("share_links")
    op.drop_index(op.f("ix_model_settings_audit_created_at"), table_name="model_settings_audit")
    op.drop_table("model_settings_audit")
