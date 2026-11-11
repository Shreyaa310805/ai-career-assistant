"""Private audio metadata on existing interview answers."""
from alembic import op
import sqlalchemy as sa

revision = "0009_interview_audio"
down_revision = "0008_interview_question_target"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("interview_answers", sa.Column("audio_storage_key", sa.String(255), nullable=True))
    op.add_column("interview_answers", sa.Column("audio_mime_type", sa.String(80), nullable=True))
    op.add_column("interview_answers", sa.Column("audio_size_bytes", sa.Integer(), nullable=True))


def downgrade():
    for name in ("audio_size_bytes", "audio_mime_type", "audio_storage_key"):
        op.drop_column("interview_answers", name)
