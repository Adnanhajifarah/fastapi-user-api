"""create favorites

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-14

The join table between users and movies that feeds the recommender's taste
profile. Two constraint decisions here are the interesting part:

* ON DELETE CASCADE on both foreign keys. A favorite has no meaning once either
  side is gone, so the database cleans up rather than leaving orphan rows that
  application code has to remember to handle.
* A composite unique constraint on (user_id, movie_id). Favoriting the same
  film twice is not a second favorite; the database rejects it rather than
  relying on every future call site to check first.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "favorites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "movie_id",
            sa.Integer(),
            sa.ForeignKey("movies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "uq_favorites_user_movie", "favorites", ["user_id", "movie_id"]
    )
    # "Every favorite for this user" is the recommender's hot path — it runs on
    # each recommendation request to build the taste profile.
    op.create_index("ix_favorites_user_id", "favorites", ["user_id"])


def downgrade() -> None:
    op.drop_table("favorites")
