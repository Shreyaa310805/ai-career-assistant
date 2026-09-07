"""add persisted interview questions

Revision ID: 0005_interview_questions
Revises: 0004_interviews
Create Date: 2026-09-04
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_interview_questions"
down_revision = "0004_interviews"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "interview_questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("interview_id", sa.Uuid(), nullable=False),
        sa.Column("question_number", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("topic", sa.String(length=160), nullable=False),
        sa.Column("question_type", sa.String(length=80), nullable=False),
        sa.Column("difficulty", sa.String(length=20), nullable=False),
        sa.Column("expected_skills", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("interview_id", "question_number", name="uq_interview_question_number"),
    )
    op.create_index("ix_interview_questions_interview_id", "interview_questions", ["interview_id"])


def downgrade():
    op.drop_index("ix_interview_questions_interview_id", table_name="interview_questions")
    op.drop_table("interview_questions")
