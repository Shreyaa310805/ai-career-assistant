"""add interview confidence scoring, session summary, and history index

Revision ID: 0007_interview_review
Revises: 0006_interview_answers
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_interview_review"
down_revision = "0006_interview_answers"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "interview_answer_evaluations",
        sa.Column("confidence_score", sa.Integer(), nullable=False, server_default="50"),
    )
    op.add_column(
        "interview_answer_evaluations",
        sa.Column("confidence_rationale", sa.Text(), nullable=False, server_default=""),
    )

    op.add_column("interviews", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("interviews", sa.Column("recommendation", sa.String(length=20), nullable=True))

    op.create_index(
        "ix_interviews_application_id_created_at",
        "interviews",
        ["application_id", "created_at"],
    )
    op.create_index(
        "ix_interviews_application_id_status",
        "interviews",
        ["application_id", "status"],
    )


def downgrade():
    op.drop_index("ix_interviews_application_id_status", table_name="interviews")
    op.drop_index("ix_interviews_application_id_created_at", table_name="interviews")
    op.drop_column("interviews", "recommendation")
    op.drop_column("interviews", "summary")
    op.drop_column("interview_answer_evaluations", "confidence_rationale")
    op.drop_column("interview_answer_evaluations", "confidence_score")
