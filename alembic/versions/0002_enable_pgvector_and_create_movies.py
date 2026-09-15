"""enable pgvector and create movies

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-14

Creating the extension inside a migration (rather than by hand in psql) is
deliberate: it means a fresh database — including the test database and
whatever managed Postgres this eventually deploys to — gets pgvector without
anyone remembering to run a manual step.

Note the embedding column is 384 dimensions, which is fixed by the choice of
sentence-transformers all-MiniLM-L6-v2. Changing embedding models later means a
new migration, because the column type itself encodes the dimension.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "movies",
        sa.Column("id", sa.Integer(), primary_key=True),
        # TMDB's own identifier. Unique so re-running the ingest script upserts
        # rather than duplicating the catalog — ingestion must be idempotent.
        sa.Column("tmdb_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("overview", sa.Text(), nullable=True),
        sa.Column("genres", sa.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("release_year", sa.SmallInteger(), nullable=True),
        sa.Column("popularity", sa.Float(), nullable=True),
        sa.Column("poster_path", sa.Text(), nullable=True),
        # Nullable because rows are ingested first and embedded in a separate
        # backfill pass; a NULL embedding marks a row the backfill still owes.
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_unique_constraint("uq_movies_tmdb_id", "movies", ["tmdb_id"])

    # Supports "most popular first" listings and gives the ingest script a cheap
    # way to page through the catalog.
    op.create_index("ix_movies_popularity", "movies", [sa.text("popularity DESC")])

    # Lets the backfill find unembedded rows without scanning the whole table.
    op.create_index(
        "ix_movies_missing_embedding",
        "movies",
        ["id"],
        postgresql_where=sa.text("embedding IS NULL"),
    )

    # No index on `embedding` on purpose. At a few thousand rows an exact
    # sequential scan is both fast enough and MORE accurate than an approximate
    # index (HNSW/IVFFlat trade recall for speed). An index gets added when the
    # catalog is large enough for the scan to actually hurt — and that decision
    # should be driven by a measurement, not by habit.


def downgrade() -> None:
    op.drop_table("movies")
    # The extension is intentionally NOT dropped. Other objects in the database
    # may depend on it, and dropping an extension is not safely reversible.
