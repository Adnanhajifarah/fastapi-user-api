"""Tests for turning raw TMDB payloads into database rows.

No network and no database here. parse_movie is a pure function, so a plain
dictionary is enough to test it - which is the reason the TMDB client and the
parsing live in different places from the code that writes to Postgres.
"""

from app.ingest import deduplicate
from app.tmdb import parse_movie, parse_release_year

GENRE_MAP = {28: "Action", 878: "Science Fiction", 18: "Drama"}

# Shaped like a real TMDB /movie/popular result.
INTERSTELLAR = {
    "id": 157336,
    "title": "Interstellar",
    "overview": "The adventures of a group of explorers...",
    "genre_ids": [12, 18, 878],
    "release_date": "2014-11-05",
    "popularity": 142.5,
    "poster_path": "/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg",
}


def test_parse_movie_extracts_expected_fields():
    row = parse_movie(INTERSTELLAR, GENRE_MAP)

    assert row["tmdb_id"] == 157336
    assert row["title"] == "Interstellar"
    assert row["release_year"] == 2014
    assert row["popularity"] == 142.5


def test_parse_movie_maps_known_genre_ids_and_drops_unknown_ones():
    row = parse_movie(INTERSTELLAR, GENRE_MAP)

    # 18 and 878 are in the map; 12 (Adventure) is not, so it is dropped rather
    # than stored as a bare number or crashing.
    assert row["genres"] == ["Drama", "Science Fiction"]


def test_parse_movie_returns_none_when_unusable():
    assert parse_movie({"title": "No id here"}, GENRE_MAP) is None
    assert parse_movie({"id": 1, "title": ""}, GENRE_MAP) is None
    assert parse_movie({"id": 1, "title": "   "}, GENRE_MAP) is None
    assert parse_movie({"id": "not-an-int", "title": "X"}, GENRE_MAP) is None


def test_parse_movie_stores_empty_overview_as_none():
    row = parse_movie({"id": 1, "title": "X", "overview": ""}, GENRE_MAP)

    # NULL means "no description", which is different from a blank string.
    assert row["overview"] is None


def test_parse_movie_tolerates_missing_optional_fields():
    row = parse_movie({"id": 1, "title": "X"}, GENRE_MAP)

    assert row["genres"] == []
    assert row["release_year"] is None
    assert row["popularity"] is None
    assert row["poster_path"] is None


def test_parse_release_year_handles_bad_input():
    assert parse_release_year("2014-11-05") == 2014
    assert parse_release_year("") is None
    assert parse_release_year(None) is None
    assert parse_release_year("not-a-date") is None


def test_deduplicate_keeps_one_row_per_tmdb_id():
    rows = [
        {"tmdb_id": 1, "title": "First"},
        {"tmdb_id": 2, "title": "Second"},
        {"tmdb_id": 1, "title": "First again"},
    ]

    result = deduplicate(rows)

    # TMDB's popular list reshuffles between requests, so the same film can
    # arrive on two pages. Postgres rejects a batch that updates one row twice.
    assert len(result) == 2
    assert {r["tmdb_id"] for r in result} == {1, 2}
