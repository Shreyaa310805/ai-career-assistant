"""Subscription entitlements and interview trial.

Revision ID: 0007_subscriptions
Revises: 0006_interview_answers
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_subscriptions"
down_revision = "0006_interview_answers"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("interview_credits", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("trial_used", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("pro_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("interviews", sa.Column("is_trial", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table("subscriptions",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("plan_id", sa.String(80), nullable=False),
        sa.Column("interval", sa.String(10), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("paid_count", sa.Integer(), nullable=False),
        sa.Column("cancel_at_cycle_end", sa.Boolean(), nullable=False))
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_table("subscription_charges",
        sa.Column("payment_id", sa.String(80), primary_key=True),
        sa.Column("subscription_id", sa.String(80), sa.ForeignKey("subscriptions.id"), nullable=False))
    op.create_table("interview_usage",
        sa.Column("interview_id", sa.Uuid(), sa.ForeignKey("interviews.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("credits_charged", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "request_id", name="uq_interview_usage_request"))
    op.create_index("ix_interview_usage_user_id", "interview_usage", ["user_id"])
    # Existing one-time Premium purchases retain access and receive an initial allowance.
    from app.core.config import get_settings
    op.get_bind().execute(sa.text("UPDATE users SET interview_credits = :credits WHERE plan = 'PREMIUM'"),
        {"credits": get_settings().pro_monthly_interview_credits})


def downgrade():
    op.drop_index("ix_interview_usage_user_id", table_name="interview_usage")
    op.drop_table("interview_usage")
    op.drop_table("subscription_charges")
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_column("interviews", "is_trial")
    for column in ("pro_until", "trial_used", "interview_credits"):
        op.drop_column("users", column)
