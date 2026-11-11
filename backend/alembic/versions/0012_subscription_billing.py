"""Add Razorpay subscriptions and interview entitlement accounting.

Revision ID: 0012_subscription_billing
Revises: 0011_audio_delivery_signals
"""
from alembic import op
import sqlalchemy as sa


revision = "0012_subscription_billing"
down_revision = "0011_audio_delivery_signals"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("interview_credits", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("trial_used", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("pro_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("interviews", sa.Column("is_trial", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.String(80), nullable=False),
        sa.Column("interval", sa.String(10), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("paid_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("credit_limit", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cancel_at_cycle_end", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index(
        "uq_subscription_open_user",
        "subscriptions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status NOT IN ('cancelled', 'completed', 'expired')"),
        sqlite_where=sa.text("status NOT IN ('cancelled', 'completed', 'expired')"),
    )
    op.create_table(
        "subscription_charges",
        sa.Column("payment_id", sa.String(80), primary_key=True),
        sa.Column("subscription_id", sa.String(80), sa.ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False),
    )
    op.create_table(
        "interview_usage",
        sa.Column("interview_id", sa.Uuid(), sa.ForeignKey("interviews.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("credits_charged", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "request_id", name="uq_interview_usage_request"),
    )
    op.create_index("ix_interview_usage_user_id", "interview_usage", ["user_id"])
    # Existing one-time Premium accounts keep access and receive the default allowance.
    from app.core.config import get_settings
    op.get_bind().execute(
        sa.text("UPDATE users SET interview_credits = :credits WHERE plan = 'PREMIUM'"),
        {"credits": get_settings().pro_monthly_interview_credits},
    )


def downgrade():
    op.drop_index("ix_interview_usage_user_id", table_name="interview_usage")
    op.drop_table("interview_usage")
    op.drop_table("subscription_charges")
    op.drop_index("uq_subscription_open_user", table_name="subscriptions")
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_column("interviews", "is_trial")
    op.drop_column("users", "pro_until")
    op.drop_column("users", "trial_used")
    op.drop_column("users", "interview_credits")
