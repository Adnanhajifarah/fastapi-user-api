"""Compute embeddings for films that do not have one yet.

    python -m app.backfill

Separate from ingestion on purpose. Ingestion is network-bound against TMDB;
embedding is compute-bound against a local model. Keeping them apart means
either can be re-run alone - and when the upsert clears a stale embedding
because a film's text changed, this picks up just that film rather than
recomputing the whole catalog.

Finding the work is cheap: the query below matches the partial index created in
migration 0002 (`WHERE embedding IS NULL`), so Postgres reads an index of only
the outstanding rows instead of scanning every film.
"""

import argparse

from psycopg2.extras import execute_values

from app.database import get_cursor
from app.embeddings import embed_texts, movie_text


def pending_count() -> int:
    with get_cursor() as cur:
        cur.execute("SELECT count(*) FROM movies WHERE embedding IS NULL")
        return cur.fetchone()[0]


def fetch_unembedded(limit: int) -> list[tuple]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, title, overview, genres
            FROM movies
            WHERE embedding IS NULL
            ORDER BY id
            LIMIT %s
            """,
            (limit,),
        )
        return cur.fetchall()


def _vector_literal(vector: list[float]) -> str:
    """Render a vector the way pgvector reads it from text: [0.1,0.2,...].

    Passing it as text and casting with ::vector avoids having to register a
    psycopg2 type adapter on every connection the pool hands out.
    """
    return "[" + ",".join(str(value) for value in vector) + "]"


def store_embeddings(rows: list[tuple[int, list[float]]]) -> int:
    """Write embeddings for the given (movie id, vector) pairs."""
    if not rows:
        return 0

    values = [(movie_id, _vector_literal(vector)) for movie_id, vector in rows]

    with get_cursor(commit=True) as cur:
        execute_values(
            cur,
            """
            UPDATE movies AS m
            SET embedding = incoming.embedding::vector,
                updated_at = now()
            FROM (VALUES %s) AS incoming(id, embedding)
            WHERE m.id = incoming.id
            """,
            values,
            page_size=len(values),
        )
        return cur.rowcount


def run_backfill(batch_size: int = 64) -> int:
    """Embed every film still missing an embedding. Returns how many were done."""
    total = 0
    remaining = pending_count()
    if remaining == 0:
        print("Nothing to embed - every film already has an embedding.")
        return 0

    print(f"{remaining} films need embedding.")

    while True:
        batch = fetch_unembedded(batch_size)
        if not batch:
            break

        texts = [
            movie_text(title=title, overview=overview, genres=genres)
            for (_id, title, overview, genres) in batch
        ]
        vectors = embed_texts(texts, batch_size=batch_size)

        written = store_embeddings(
            [(row[0], vector) for row, vector in zip(batch, vectors)]
        )
        total += written
        print(f"  embedded {total}/{remaining}")

    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Films embedded per model call (default: 64)",
    )
    args = parser.parse_args()

    done = run_backfill(batch_size=args.batch_size)
    print(f"\nDone. Embedded {done} films.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
