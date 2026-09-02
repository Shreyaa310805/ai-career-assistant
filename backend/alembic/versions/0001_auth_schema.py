"""create authentication schema

Revision ID: 0001_auth_schema
Revises:
Create Date: 2026-09-01
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_auth_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    plan_enum_type = sa.Enum(
        "FREE",
        "PREMIUM",
        name="plan_type",
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "plan",
            plan_enum_type,
            server_default="FREE",
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_index(
        "ix_users_email",
        "users",
        ["email"],
        unique=False,
    )

    op.create_table(
        "revoked_tokens",
        sa.Column("jti", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("jti"),
    )


def downgrade() -> None:
    op.drop_table("revoked_tokens")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    sa.Enum(
        "FREE",
        "PREMIUM",
        name="plan_type",
    ).drop(op.get_bind(), checkfirst=True)