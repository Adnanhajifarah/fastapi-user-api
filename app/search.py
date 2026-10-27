"""Two ways to find films, so they can be compared.

`vector_search` embeds the query and asks Postgres for the nearest film
vectors - semantic matching, which can connect "a cerebral space film" to a
synopsis that never uses either word.

`keyword_search` is deliberately here as a baseline, using Postgres's built-in
full-text search and no embeddings at all. It exists to answer the question an
interviewer will ask: how do you know the vector search is actually better?
Without a baseline, "it returns plausible results" is the only claim available,
and that is not a measurement. Some queries the keyword search wins outright -
exact titles, proper nouns, specific words the synopsis really contains.
"""

from typing import Any

from app.database import get_cursor
from app.embeddings import embed_query

# Columns both searches return, so results are directly comparable.
RESULT_COLUMNS = "id, tmdb_id, title, release_year, genres"


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(str(value) for value in vector) + "]"


def vector_search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Find films whose meaning is closest to the query.

    The `<=>` operator is pgvector's cosine distance: 0 means the vectors point
    the same way, larger means further apart. ORDER BY on that operator is the
    whole search - "nearest neighbours" is just a sort.

    Reported as similarity (1 - distance) because "higher is better" reads more
    naturally than "lower is better".

    Films with no embedding yet are excluded rather than silently ranked last.
    """
    query_vector = _vector_literal(embed_query(query))

    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT {RESULT_COLUMNS},
                   1 - (embedding <=> %(vector)s::vector) AS score
            FROM movies
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %(vector)s::vector
            LIMIT %(limit)s
            """,
            {"vector": query_vector, "limit": limit},
        )
        return [_row_to_dict(row) for row in cur.fetchall()]


def keyword_search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Find films whose text literally contains the query's words.

    to_tsvector breaks the text into normalised search terms - lowercasing, and
    reducing words to stems so "exploring" matches "explorer".

    The query terms are joined with OR rather than AND, which matters a lot. By
    default Postgres requires every term to be present, so a conversational
    query like "a heist with a crew of professionals" matches nothing at all -
    no synopsis contains all those words. That would make this a straw-man
    baseline that the vector search beats for the wrong reason. Joining with OR
    asks "which films contain any of these words", ranked by how well they
    match, which is a fair comparison. Postgres discards English stopwords
    ("a", "with", "of") on its own.

    The tsvector is computed on the fly here. That is fine at a few thousand
    films; the production version would store it in a generated column with a
    GIN index so it is not recomputed on every search.
    """
    # websearch_to_tsquery understands the literal word OR, and sanitises
    # whatever else is in the string, so this stays injection-safe.
    or_query = " OR ".join(word for word in query.split() if word)

    with get_cursor() as cur:
        cur.execute(
            f"""
            WITH searchable AS (
                SELECT {RESULT_COLUMNS},
                       to_tsvector('english', title || ' ' || coalesce(overview, '')) AS document
                FROM movies
            )
            SELECT {RESULT_COLUMNS},
                   ts_rank(document, websearch_to_tsquery('english', %(query)s)) AS score
            FROM searchable
            WHERE document @@ websearch_to_tsquery('english', %(query)s)
            ORDER BY score DESC
            LIMIT %(limit)s
            """,
            {"query": or_query, "limit": limit},
        )
        return [_row_to_dict(row) for row in cur.fetchall()]


def _row_to_dict(row: tuple) -> dict[str, Any]:
    movie_id, tmdb_id, title, release_year, genres, score = row
    return {
        "id": movie_id,
        "tmdb_id": tmdb_id,
        "title": title,
        "release_year": release_year,
        "genres": genres,
        "score": round(float(score), 4),
    }


def compare(query: str, limit: int = 5) -> dict[str, list[dict[str, Any]]]:
    """Run both searches on one query. Used by the eval harness."""
    return {
        "query": query,
        "vector": vector_search(query, limit=limit),
        "keyword": keyword_search(query, limit=limit),
    }
