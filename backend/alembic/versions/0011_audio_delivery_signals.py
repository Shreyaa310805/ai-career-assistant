"""Persist transcript-derived audio delivery signals.

Revision ID: 0011_audio_delivery_signals
Revises: 0010_video_interview
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_audio_delivery_signals"
down_revision = "0010_video_interview"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("interview_answers", sa.Column("delivery_signals", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("interview_answers", "delivery_signals")
