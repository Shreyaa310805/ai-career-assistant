"""add interview sessions

Revision ID: 0004_interviews
Revises: 0003_payments_and_scratch
Create Date: 2026-09-03
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_interviews"
down_revision = "0003_payments_and_scratch"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "interviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("personality", sa.String(length=30), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="created", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interviews_application_id", "interviews", ["application_id"])


def downgrade():
    op.drop_index("ix_interviews_application_id", table_name="interviews")
    op.drop_table("interviews")
