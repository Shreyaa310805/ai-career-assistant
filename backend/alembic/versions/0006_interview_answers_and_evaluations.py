"""add interview answers and evaluations

Revision ID: 0006_interview_answers
Revises: 0005_interview_questions
Create Date: 2026-09-08
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_interview_answers"
down_revision = "0005_interview_questions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "interview_answers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("interview_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["interview_questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interview_answers_interview_id", "interview_answers", ["interview_id"])
    op.create_index("ix_interview_answers_question_id", "interview_answers", ["question_id"])
    op.create_table(
        "interview_answer_evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("answer_id", sa.Uuid(), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("relevance_score", sa.Integer(), nullable=False),
        sa.Column("correctness_score", sa.Integer(), nullable=False),
        sa.Column("depth_score", sa.Integer(), nullable=False),
        sa.Column("clarity_score", sa.Integer(), nullable=False),
        sa.Column("evidence_score", sa.Integer(), nullable=False),
        sa.Column("strengths", sa.JSON(), nullable=False),
        sa.Column("weaknesses", sa.JSON(), nullable=False),
        sa.Column("missing_points", sa.JSON(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["answer_id"], ["interview_answers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("answer_id", name="uq_interview_answer_evaluation_answer"),
    )
    op.create_index("ix_interview_answer_evaluations_answer_id", "interview_answer_evaluations", ["answer_id"])


def downgrade():
    op.drop_index("ix_interview_answer_evaluations_answer_id", table_name="interview_answer_evaluations")
    op.drop_table("interview_answer_evaluations")
    op.drop_index("ix_interview_answers_question_id", table_name="interview_answers")
    op.drop_index("ix_interview_answers_interview_id", table_name="interview_answers")
    op.drop_table("interview_answers")
