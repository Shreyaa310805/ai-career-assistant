"""create applications

Revision ID: 0002_applications
Revises: 0001_auth_schema
Create Date: 2026-09-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_applications"
down_revision = "0001_auth_schema"
branch_labels = None
depends_on = None


def upgrade():
    status_type = sa.Enum(
        "SAVED",
        "APPLIED",
        "INTERVIEWING",
        "OFFER",
        "REJECTED",
        name="application_status",
    )

    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("company", sa.String(length=160), nullable=False),
        sa.Column("role", sa.String(length=160), nullable=False),
        sa.Column(
            "status",
            status_type,
            server_default="SAVED",
            nullable=False,
        ),
        sa.Column("location", sa.String(length=160), nullable=True),
        sa.Column("job_url", sa.String(length=2048), nullable=True),
        sa.Column("job_description", sa.Text(), nullable=True),
        sa.Column("applied_at", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_applications_user_id",
        "applications",
        ["user_id"],
    )


def downgrade():
    op.drop_index(
        "ix_applications_user_id",
        table_name="applications",
    )
    op.drop_table("applications")

    sa.Enum(
        "SAVED",
        "APPLIED",
        "INTERVIEWING",
        "OFFER",
        "REJECTED",
        name="application_status",
    ).drop(op.get_bind(), checkfirst=True)