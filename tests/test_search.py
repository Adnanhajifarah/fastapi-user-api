"""Search tests, run against the seeded catalog.

These are integration tests: they need a database with films that have
embeddings. They skip rather than fail when the catalog is empty, so a fresh
clone can run the suite before anyone has run `python -m app.seed`.
"""

import pytest

from app.database import get_cursor
from app.search import keyword_search, vector_search


def embedded_film_count() -> int:
    with get_cursor() as cur:
        cur.execute("SELECT count(embedding) FROM movies")
        return cur.fetchone()[0]


requires_catalog = pytest.mark.skipif(
    embedded_film_count() == 0,
    reason="no embedded films; run `python -m app.seed` then `python -m app.backfill`",
)


@requires_catalog
@pytest.mark.slow
def test_vector_search_returns_the_requested_number_of_results():
    results = vector_search("a science fiction film", limit=3)

    assert len(results) == 3


@requires_catalog
@pytest.mark.slow
def test_vector_search_results_are_ordered_by_descending_score():
    results = vector_search("a crime thriller", limit=5)

    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


@requires_catalog
@pytest.mark.slow
def test_vector_search_finds_the_right_film_for_a_plot_query():
    """A plot query is where embeddings are strongest and most confident.

    This one is a deliberate canary: the seed catalog has exactly one film about
    a linguist communicating with visitors, and it scores roughly twice the
    runner-up. If this starts failing, something about the embedding pipeline
    has broken - a changed model, changed text construction, or a stale backfill.
    """
    results = vector_search("aliens land on earth and a linguist learns to communicate", limit=3)

    assert results[0]["title"] == "Arrival"
    assert results[0]["score"] > results[1]["score"] * 1.5


@requires_catalog
def test_keyword_search_matches_on_a_distinctive_word():
    # No embeddings involved; this is the baseline the vector search is measured
    # against. "linguist" appears in exactly one synopsis.
    results = keyword_search("linguist", limit=3)

    assert results
    assert results[0]["title"] == "Arrival"


@requires_catalog
def test_keyword_search_returns_nothing_for_absent_words():
    assert keyword_search("zzzznonexistentword", limit=3) == []
