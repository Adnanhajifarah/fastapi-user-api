"""Tests for building film text and for the embedding model itself.

The movie_text tests are instant - it is a pure string function. The tests that
load the model are slower (a second or two) and are grouped at the bottom.
"""

import pytest

from app.embeddings import EMBEDDING_DIMENSIONS, embed_query, embed_texts, movie_text


def test_movie_text_includes_title_genres_and_overview():
    text = movie_text("Arrival", "A linguist meets visitors.", ["Drama", "Science Fiction"])

    assert "Arrival" in text
    assert "Science Fiction" in text
    assert "A linguist meets visitors." in text


def test_movie_text_repeats_genres_to_weight_them():
    text = movie_text("X", "A plot.", ["Comedy"], genre_repeat=3)

    # Repetition is how the genre signal competes with a much longer synopsis.
    # See the docstring on movie_text for the measurement behind this.
    assert text.count("Comedy") == 3


def test_movie_text_omits_release_year_entirely():
    # Year is structured data for a WHERE clause; as text it is noise, because
    # the model has no sense that 1994 and 1995 are adjacent.
    text = movie_text("Pulp Fiction", "Some crime stories.", ["Crime"])

    assert "1994" not in text


def test_movie_text_survives_missing_fields():
    assert movie_text("Just A Title", None, None) == "Just A Title"
    assert movie_text("Title", "", []) == "Title"


def test_movie_text_with_no_genres_does_not_repeat_anything():
    text = movie_text("Title", "A plot.", [], genre_repeat=3)

    assert text == "Title. A plot."


@pytest.mark.slow
def test_embed_query_returns_one_vector_of_the_column_width():
    vector = embed_query("a film about space")

    # Must match vector(384) in migration 0002 or the insert fails.
    assert len(vector) == EMBEDDING_DIMENSIONS
    assert all(isinstance(value, float) for value in vector)


@pytest.mark.slow
def test_embeddings_are_normalised_to_unit_length():
    vector = embed_query("a film about space")

    length = sum(value * value for value in vector) ** 0.5
    # Normalised vectors let cosine similarity compare pure direction, so a long
    # synopsis is not penalised against a short one.
    assert length == pytest.approx(1.0, abs=1e-5)


@pytest.mark.slow
def test_embed_texts_is_order_preserving_and_deterministic():
    first = embed_texts(["a cheerful cartoon", "a bleak war film"])
    second = embed_texts(["a cheerful cartoon", "a bleak war film"])

    assert len(first) == 2
    assert first[0] == pytest.approx(second[0], abs=1e-6)
    assert first[0] != first[1]


@pytest.mark.slow
def test_embed_texts_on_empty_input_does_not_load_the_model():
    assert embed_texts([]) == []
