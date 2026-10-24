"""create churn tables

Revision ID: 3f9a1c2b7d4e
Revises: 55e1b33fc1f7
Create Date: 2026-10-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "3f9a1c2b7d4e"
down_revision: Union[str, Sequence[str], None] = "55e1b33fc1f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "accounts",
        sa.Column("id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("balance", sa.BigInteger(), nullable=False),
        sa.Column("withdraw_balance", sa.BigInteger(), nullable=False),
        sa.Column("total_replenished", sa.BigInteger(), nullable=False),
        sa.Column("bonus_balance", sa.BigInteger(), nullable=False),
        sa.Column("bonus_state", sa.Text(), nullable=False),
        sa.CheckConstraint("balance >= 0", name=op.f("ck_accounts_balance_non_negative")),
        sa.CheckConstraint("withdraw_balance >= 0", name=op.f("ck_accounts_withdraw_balance_non_negative")),
        sa.CheckConstraint("total_replenished >= 0", name=op.f("ck_accounts_total_replenished_non_negative")),
        sa.CheckConstraint("bonus_balance >= 0", name=op.f("ck_accounts_bonus_balance_non_negative")),
        sa.CheckConstraint("bonus_state IN ('locked', 'unlocked')", name=op.f("ck_accounts_bonus_state_valid")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
        sa.UniqueConstraint("email", name=op.f("uq_accounts_email")),
    )

    op.create_table(
        "services",
        sa.Column("id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("payment_term", sa.Text(), nullable=False),
        sa.Column("auto_prolong", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("price", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "payment_term IN ('hour', 'week', 'month', 'quarter_year', 'half_year', 'year')",
            name=op.f("ck_services_payment_term_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'blocked', 'deleted', 'suspended', 'prolong_wait')",
            name=op.f("ck_services_status_valid"),
        ),
        sa.CheckConstraint("price >= 0", name=op.f("ck_services_price_non_negative")),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["accounts.id"], name=op.f("fk_services_owner_id_accounts"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_services")),
    )
    op.create_index(op.f("ix_services_owner_id"), "services", ["owner_id"], unique=False)

    op.create_table(
        "transactions",
        sa.Column("id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("service_id", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("amount >= 0 AND amount <= 1000", name=op.f("ck_transactions_amount_range")),
        sa.CheckConstraint(
            "status IN ('performed', 'not_performed')", name=op.f("ck_transactions_status_valid")
        ),
        sa.CheckConstraint("type IN ('prolong', 'order')", name=op.f("ck_transactions_type_valid")),
        sa.ForeignKeyConstraint(
            ["service_id"], ["services.id"], name=op.f("fk_transactions_service_id_services"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
    )
    op.create_index(op.f("ix_transactions_service_id"), "transactions", ["service_id"], unique=False)

    op.create_table(
        "model_settings",
        sa.Column("id", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column(
            "data", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("id = 1", name=op.f("ck_model_settings_singleton")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_settings")),
    )

    op.create_table(
        "risk_results",
        sa.Column("account_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=True),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("reason_short", sa.Text(), nullable=False),
        sa.Column("reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expected_loss_cents", sa.BigInteger(), nullable=False),
        sa.Column(
            "details", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("score >= 0 AND score <= 100", name=op.f("ck_risk_results_score_range")),
        sa.CheckConstraint(
            "level IN ('high', 'medium', 'low', 'no_data')", name=op.f("ck_risk_results_level_valid")
        ),
        sa.CheckConstraint(
            "expected_loss_cents >= 0", name=op.f("ck_risk_results_expected_loss_non_negative")
        ),
        sa.CheckConstraint(
            "(level = 'no_data') = (score IS NULL)", name=op.f("ck_risk_results_no_data_iff_null_score")
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name=op.f("fk_risk_results_account_id_accounts"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("account_id", name=op.f("pk_risk_results")),
    )
    op.create_index(op.f("ix_risk_results_level"), "risk_results", ["level"], unique=False)

    op.create_table(
        "risk_summary",
        sa.Column("id", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column("version", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("reason", sa.Text(), server_default=sa.text("'init'"), nullable=False),
        sa.Column("customers_total", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "by_level", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column("expected_loss_cents", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("loss_explanation", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recalculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("id = 1", name=op.f("ck_risk_summary_singleton")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_summary")),
    )

    # Строки-синглтоны: настройки и сводка существуют всегда
    op.execute("INSERT INTO model_settings (id) VALUES (1)")
    op.execute("INSERT INTO risk_summary (id) VALUES (1)")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("risk_summary")
    op.drop_index(op.f("ix_risk_results_level"), table_name="risk_results")
    op.drop_table("risk_results")
    op.drop_table("model_settings")
    op.drop_index(op.f("ix_transactions_service_id"), table_name="transactions")
    op.drop_table("transactions")
    op.drop_index(op.f("ix_services_owner_id"), table_name="services")
    op.drop_table("services")
    op.drop_table("accounts")
