"""Reserved migration revision for the deferred question-pack feature.

Revision ID: 0013_interview_question_packs
Revises: 0012_subscription_billing

The feature was put on hold before deployment, so fresh databases should not
create its table. Keep this no-op revision so a database that already recorded
the earlier local draft can still resolve its Alembic head.
"""

revision = "0013_interview_question_packs"
down_revision = "0012_subscription_billing"
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
