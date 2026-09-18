"""payments, scratch applications, extended status enum

Revision ID: 0003_payments_and_scratch
Revises: 0002_applications
Create Date: 2026-09-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_payments_and_scratch"
down_revision = "0002_applications"
branch_labels = None
depends_on = None

NEW_STATUSES = ("SELECTED", "OFFER_DECLINED")


def upgrade():
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        # plan_type already exists from 0001; do not re-create it on Postgres.
        # `create_type` is only honored by the dialect-specific
        # postgresql.ENUM — plain sa.Enum silently ignores it.
        sa.Column(
            "plan",
            postgresql.ENUM("FREE", "PREMIUM", name="plan_type", create_type=False)
            if is_postgres
            else sa.Enum("FREE", "PREMIUM", name="plan_type"),
            nullable=False,
        ),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("provider", sa.String(length=32), server_default="mock", nullable=False),
        sa.Column(
            "status",
            sa.Enum("SUCCEEDED", "FAILED", name="payment_status"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])

    op.add_column(
        "applications",
        sa.Column("is_scratch", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_index("ix_applications_is_scratch", "applications", ["is_scratch"])

    if is_postgres:
        # ALTER TYPE ... ADD VALUE cannot run inside a transaction block.
        with op.get_context().autocommit_block():
            for value in NEW_STATUSES:
                op.execute(f"ALTER TYPE application_status ADD VALUE IF NOT EXISTS '{value}'")


def downgrade():
    op.drop_index("ix_applications_is_scratch", table_name="applications")
    op.drop_column("applications", "is_scratch")
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_table("payments")
    # Postgres cannot remove a value from an enum type; the extra statuses are
    # left in place. Rows using them must be migrated by hand before reverting.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS payment_status")
