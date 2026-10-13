"""Client for The Movie Database (TMDB) API.

This module knows how to fetch and clean up film data. It knows nothing about
Postgres. Keeping the two apart means the messy part - turning whatever TMDB
sends back into tidy rows - can be tested with a plain dictionary, no network
and no database required. See tests/test_tmdb.py.
"""

import os
import time
from typing import Any, Iterator

import httpx

TMDB_BASE_URL = "https://api.themoviedb.org/3"

# TMDB asks clients to stay reasonable; a short pause between pages keeps this
# well inside their limits. Ingestion is a background job, so waiting costs
# nothing that matters.
SECONDS_BETWEEN_REQUESTS = 0.25


class TMDBError(RuntimeError):
    """Raised when TMDB returns something unusable."""


class TMDBClient:
    """Thin wrapper over the TMDB HTTP API.

    TMDB has two authentication styles. The older v3 style puts a 32-character
    key in the query string; the newer v4 style sends a long token in an
    Authorization header. Which one you have depends on where you copied it
    from, so this detects it rather than making you care.
    """

    def __init__(self, api_key: str | None = None, timeout: float = 10.0):
        key = api_key or os.environ.get("TMDB_API_KEY", "")
        if not key:
            raise TMDBError(
                "TMDB_API_KEY is not set. Get a free key at "
                "https://www.themoviedb.org/settings/api and export it."
            )

        # v4 read access tokens are JSON Web Tokens and always start with "eyJ".
        self._is_bearer_token = key.startswith("eyJ")
        self._key = key

        headers = {"accept": "application/json"}
        if self._is_bearer_token:
            headers["Authorization"] = f"Bearer {key}"

        self._client = httpx.Client(
            base_url=TMDB_BASE_URL, headers=headers, timeout=timeout
        )

    def __enter__(self) -> "TMDBClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _get(self, path: str, **params) -> dict[str, Any]:
        if not self._is_bearer_token:
            params["api_key"] = self._key

        response = self._client.get(path, params=params)
        if response.status_code == 401:
            raise TMDBError(
                "TMDB rejected the API key (401). Check TMDB_API_KEY is correct."
            )
        response.raise_for_status()
        return response.json()

    def fetch_genre_map(self) -> dict[int, str]:
        """Return {genre_id: genre_name}.

        Film results carry genre_ids like [28, 12], not names. This is fetched
        once and reused for every page rather than per film.
        """
        payload = self._get("/genre/movie/list", language="en-US")
        return {g["id"]: g["name"] for g in payload.get("genres", [])}

    def iter_popular_movies(self, pages: int) -> Iterator[dict[str, Any]]:
        """Yield raw film results from TMDB's popular list, one page at a time.

        A generator rather than a list so the caller can start writing rows
        before every page has been fetched, and so memory stays flat no matter
        how many pages are requested.
        """
        for page in range(1, pages + 1):
            payload = self._get(
                "/movie/popular",
                page=page,
                language="en-US",
                include_adult=False,
            )
            results = payload.get("results", [])
            if not results:
                break

            yield from results

            # TMDB caps the popular list; stop early rather than re-requesting
            # the final page over and over.
            if page >= payload.get("total_pages", page):
                break

            time.sleep(SECONDS_BETWEEN_REQUESTS)


def parse_release_year(release_date: Any) -> int | None:
    """Pull the year out of a TMDB release_date.

    TMDB sends "2014-11-05", but also sometimes an empty string or nothing at
    all for unreleased or poorly catalogued films, so this never assumes.
    """
    if not isinstance(release_date, str) or len(release_date) < 4:
        return None
    try:
        return int(release_date[:4])
    except ValueError:
        return None


def parse_movie(result: dict[str, Any], genre_map: dict[int, str]) -> dict[str, Any] | None:
    """Turn one raw TMDB result into a row ready for the movies table.

    Returns None for records that are unusable - no id, or no title - rather
    than writing junk. External APIs return surprising things and the database
    is the wrong place to discover that.

    This function is pure: same input, same output, no network, no database.
    That is what makes it straightforward to test.
    """
    tmdb_id = result.get("id")
    title = (result.get("title") or "").strip()

    if not isinstance(tmdb_id, int) or not title:
        return None

    overview = (result.get("overview") or "").strip()
    genre_ids = result.get("genre_ids") or []
    genres = [genre_map[gid] for gid in genre_ids if gid in genre_map]

    popularity = result.get("popularity")
    if not isinstance(popularity, (int, float)):
        popularity = None

    poster_path = result.get("poster_path") or None

    return {
        "tmdb_id": tmdb_id,
        "title": title,
        # Empty overviews are stored as NULL rather than "", so "we have no
        # description" is distinguishable from "the description is blank".
        "overview": overview or None,
        "genres": genres,
        "release_year": parse_release_year(result.get("release_date")),
        "popularity": float(popularity) if popularity is not None else None,
        "poster_path": poster_path,
    }
