"""Load the TMDB film catalog into the movies table.

Run as a command-line script, never from a request handler: it makes hundreds
of outbound HTTP calls and takes minutes, which is not something a web request
should ever do.

    python -m app.ingest --pages 100

Re-running is safe. Every film is matched on its TMDB id, so a second run
updates existing rows instead of duplicating them.
"""

import argparse
import sys
from typing import Any, Iterable

from psycopg2.extras import execute_values

from app.database import get_cursor
from app.tmdb import TMDBClient, TMDBError, parse_movie

COLUMNS = (
    "tmdb_id",
    "title",
    "overview",
    "genres",
    "release_year",
    "popularity",
    "poster_path",
)

# The heart of the script.
#
# ON CONFLICT (tmdb_id) DO UPDATE is what makes re-running safe: when a film is
# already present, its row is refreshed instead of a duplicate being created.
# This is why migration 0002 put a unique constraint on tmdb_id - without it
# there is no conflict for Postgres to detect, and nothing to key the update on.
#
# The CASE on embedding is the subtle part. An embedding is a numeric summary of
# the title and overview. If TMDB has since changed either of those, the stored
# embedding describes text that no longer exists, so it is set back to NULL and
# the backfill will recompute it. If the text is unchanged the embedding is left
# alone - recomputing thousands of unchanged films would be pure waste.
#
# RETURNING (xmax = 0) is a Postgres detail worth knowing: xmax is zero on a
# freshly inserted row and non-zero on one that was updated, so this reports how
# many films were new versus refreshed without a second query.
UPSERT_SQL = """
    INSERT INTO movies (tmdb_id, title, overview, genres, release_year, popularity, poster_path)
    VALUES %s
    ON CONFLICT (tmdb_id) DO UPDATE SET
        title        = EXCLUDED.title,
        overview     = EXCLUDED.overview,
        genres       = EXCLUDED.genres,
        release_year = EXCLUDED.release_year,
        popularity   = EXCLUDED.popularity,
        poster_path  = EXCLUDED.poster_path,
        updated_at   = now(),
        embedding    = CASE
            WHEN movies.title    IS DISTINCT FROM EXCLUDED.title
              OR movies.overview IS DISTINCT FROM EXCLUDED.overview
            THEN NULL
            ELSE movies.embedding
        END
    RETURNING (xmax = 0) AS was_inserted
"""


def deduplicate(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one row per tmdb_id, last occurrence winning.

    Necessary, not defensive. TMDB's popular list is recalculated constantly, so
    a film can slide from page 3 to page 4 between two requests and arrive
    twice. Postgres refuses a batch that tries to update the same row twice in
    one statement ("ON CONFLICT DO UPDATE command cannot affect row a second
    time"), so duplicates have to be removed before the insert, not after.
    """
    unique: dict[int, dict[str, Any]] = {}
    for row in rows:
        unique[row["tmdb_id"]] = row
    return list(unique.values())


def upsert_movies(rows: list[dict[str, Any]]) -> tuple[int, int]:
    """Write a batch of films. Returns (inserted, updated)."""
    if not rows:
        return (0, 0)

    values = [tuple(row[column] for column in COLUMNS) for row in rows]

    with get_cursor(commit=True) as cur:
        results = execute_values(
            cur, UPSERT_SQL, values, page_size=len(values), fetch=True
        )

    inserted = sum(1 for (was_inserted,) in results if was_inserted)
    return (inserted, len(results) - inserted)


def run_ingest(pages: int, batch_size: int, dry_run: bool = False) -> tuple[int, int, int]:
    """Fetch `pages` pages of popular films and write them.

    Returns (inserted, updated, skipped).
    """
    total_inserted = total_updated = skipped = 0
    batch: list[dict[str, Any]] = []

    with TMDBClient() as client:
        genre_map = client.fetch_genre_map()
        print(f"Loaded {len(genre_map)} genres from TMDB.")

        for raw in client.iter_popular_movies(pages=pages):
            row = parse_movie(raw, genre_map)
            if row is None:
                skipped += 1
                continue

            batch.append(row)

            if len(batch) >= batch_size:
                inserted, updated = _flush(batch, dry_run)
                total_inserted += inserted
                total_updated += updated
                batch = []
                print(f"  ...{total_inserted + total_updated} films processed")

    inserted, updated = _flush(batch, dry_run)
    total_inserted += inserted
    total_updated += updated

    return (total_inserted, total_updated, skipped)


def _flush(batch: list[dict[str, Any]], dry_run: bool) -> tuple[int, int]:
    rows = deduplicate(batch)
    if dry_run:
        # Report what would happen without touching the database. Everything is
        # counted as an insert because finding out otherwise would mean querying.
        return (len(rows), 0)
    return upsert_movies(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pages",
        type=int,
        default=10,
        help="TMDB pages to fetch; 20 films per page (default: 10)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Films per database write (default: 100)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and parse, but write nothing",
    )
    args = parser.parse_args()

    try:
        inserted, updated, skipped = run_ingest(
            pages=args.pages, batch_size=args.batch_size, dry_run=args.dry_run
        )
    except TMDBError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    label = "would insert" if args.dry_run else "inserted"
    print(f"\nDone. {label}: {inserted}, updated: {updated}, skipped: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
