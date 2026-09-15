"""Video interview mode and per-frame visual analysis.

Revision ID: 0010_video_interview
Revises: 0009_interview_audio
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_video_interview"
down_revision = "0009_interview_audio"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("interviews", sa.Column("mode", sa.String(10), nullable=False, server_default="text"))
    op.add_column("interviews", sa.Column("visual_score", sa.Integer(), nullable=True))
    op.add_column("interviews", sa.Column("visual_summary", sa.JSON(), nullable=True))
    op.create_table(
        "interview_visual_frames",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("interview_id", sa.Uuid(), sa.ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Uuid(), sa.ForeignKey("interview_questions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("face_visible", sa.Boolean(), nullable=False),
        sa.Column("multiple_people", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("looking_at_camera", sa.Boolean(), nullable=False),
        sa.Column("engagement_score", sa.Integer(), nullable=False),
        sa.Column("attentiveness_score", sa.Integer(), nullable=False),
        sa.Column("composure_score", sa.Integer(), nullable=False),
        sa.Column("presentation_score", sa.Integer(), nullable=False),
        sa.Column("expression", sa.String(40), nullable=False),
        sa.Column("observation", sa.Text(), nullable=False, server_default=""),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_interview_visual_frames_interview_id", "interview_visual_frames", ["interview_id"])


def downgrade():
    op.drop_index("ix_interview_visual_frames_interview_id", table_name="interview_visual_frames")
    op.drop_table("interview_visual_frames")
    for name in ("visual_summary", "visual_score", "mode"):
        op.drop_column("interviews", name)
