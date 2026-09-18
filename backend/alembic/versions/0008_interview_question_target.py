"""add interview question_target for selectable session length

Revision ID: 0008_interview_question_target
Revises: 0007_interview_review
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_interview_question_target"
down_revision = "0007_interview_review"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "interviews",
        sa.Column("question_target", sa.Integer(), nullable=False, server_default="5"),
    )


def downgrade():
    op.drop_column("interviews", "question_target")
