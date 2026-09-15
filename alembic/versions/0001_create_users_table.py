"""create users table

Revision ID: 0001
Revises:
Create Date: 2026-09-14

The users table was originally created by hand in psql, so it existed in the
database but nowhere in the repository. This migration makes it reproducible:
a fresh clone plus `alembic upgrade head` now yields the same schema.

The password column is named password_hash. The old name (password) was
misleading — nothing here ever stores a password, only a bcrypt digest of one.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        # bcrypt digests are 60 characters; 255 leaves room to migrate to a
        # different algorithm later without another schema change.
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # Enforced by the database, not just the application: two concurrent
    # signups with the same email cannot both succeed, which a SELECT-then-
    # INSERT check in Python could not prevent.
    op.create_unique_constraint("uq_users_email", "users", ["email"])


def downgrade() -> None:
    op.drop_table("users")
