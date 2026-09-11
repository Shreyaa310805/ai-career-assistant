"""Snapshot each paid allowance and constrain open subscriptions.

Revision ID: 0008_subscription_allowance
Revises: 0007_subscriptions
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_subscription_allowance"
down_revision = "0007_subscriptions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("subscriptions", sa.Column("credit_limit", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("uq_subscription_open_user", "subscriptions", ["user_id"], unique=True,
        postgresql_where=sa.text("status NOT IN ('cancelled', 'completed', 'expired')"),
        sqlite_where=sa.text("status NOT IN ('cancelled', 'completed', 'expired')"))


def downgrade():
    op.drop_index("uq_subscription_open_user", table_name="subscriptions")
    op.drop_column("subscriptions", "credit_limit")
