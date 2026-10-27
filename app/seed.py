"""Load the development seed catalog into the movies table.

    python -m app.seed

For working on search without a TMDB API key, and for giving the test suite and
the recommendation eval a fixed set of films that does not shift under them the
way TMDB's popular list does.

Uses the same upsert as the real ingest, so running both is safe in either
order.
"""

import json
from pathlib import Path

from app.ingest import upsert_movies

SEED_FILE = Path(__file__).resolve().parent.parent / "seeds" / "movies.json"


def load_seed_rows() -> list[dict]:
    """Read the seed file and shape it like parsed TMDB rows."""
    payload = json.loads(SEED_FILE.read_text())
    return [
        {
            "tmdb_id": movie["tmdb_id"],
            "title": movie["title"],
            "overview": movie.get("overview"),
            "genres": movie.get("genres", []),
            "release_year": movie.get("release_year"),
            "popularity": movie.get("popularity"),
            "poster_path": None,
        }
        for movie in payload["movies"]
    ]


def main() -> int:
    rows = load_seed_rows()
    inserted, updated = upsert_movies(rows)
    print(f"Seeded {len(rows)} films: {inserted} inserted, {updated} updated.")
    print("Next: python -m app.backfill")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
