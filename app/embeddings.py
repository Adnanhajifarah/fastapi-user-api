"""Turn film text into vectors.

An embedding is a list of numbers that stands in for a piece of text's meaning.
Texts that mean similar things get vectors that sit close together, so "find
films like this" becomes "find the nearest vectors" - arithmetic a database can
do, rather than something requiring an LLM call per search.

The model used here runs locally on the CPU and costs nothing per call. The
first run downloads roughly 90MB from Hugging Face and caches it in
~/.cache/huggingface, so that happens once.
"""

import os
from typing import Iterable, Sequence

# all-MiniLM-L6-v2 produces 384 numbers per text. That number is baked into the
# movies.embedding column (vector(384)) by migration 0002, so the two have to
# agree - hence the check in get_model() below.
MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIMENSIONS = 384

_model = None


def get_model():
    """Load the model once and reuse it.

    Loading reads ~90MB off disk and takes a second or two. Doing it at import
    time would make every `import app.something` pay that cost - including the
    test suite and any CLI script that never embeds anything. So it happens on
    first actual use and is then cached in a module-level variable.
    """
    global _model
    if _model is None:
        # Imported here rather than at module top for the same reason: importing
        # sentence_transformers pulls in PyTorch, which is slow.
        from sentence_transformers import SentenceTransformer

        device = os.environ.get("EMBEDDING_DEVICE")  # None lets it auto-select
        _model = SentenceTransformer(MODEL_NAME, device=device)

        # Renamed in sentence-transformers 6; fall back for older versions.
        if hasattr(_model, "get_embedding_dimension"):
            actual = _model.get_embedding_dimension()
        else:
            actual = _model.get_sentence_embedding_dimension()
        if actual != EMBEDDING_DIMENSIONS:
            raise RuntimeError(
                f"{MODEL_NAME} produces {actual}-dimensional vectors but the "
                f"movies.embedding column is vector({EMBEDDING_DIMENSIONS}). "
                "Changing embedding models requires a migration to alter the "
                "column, plus re-embedding every row."
            )
    return _model


# How many times the genre list is repeated in a film's text. See movie_text.
GENRE_REPEAT = int(os.environ.get("EMBEDDING_GENRE_REPEAT", "3"))


def movie_text(
    title: str,
    overview: str | None,
    genres: Sequence[str] | None,
    genre_repeat: int = GENRE_REPEAT,
) -> str:
    """Build the single string that represents a film to the model.

    This function is the most consequential thing in the file. The model only
    sees this text, so information left out of it cannot influence what counts
    as "similar" - no better model can recover what was never there.

    Release year is deliberately left OUT. To the model "1994" and "1995" are
    just tokens with no sense of adjacency, so years add noise without making
    "films from the nineties" work. Year is structured data and belongs in a
    WHERE clause, where it filters exactly.

    Genres are repeated, which looks like a hack and needs the justification:

    Queries come in two kinds. Plot queries ("aliens land and a linguist learns
    to communicate") match a synopsis directly and work well - measured at ~0.62
    similarity on the right film. Mood queries ("something gentle to watch with
    my kids") do not, because no synopsis contains the words "gentle" or "kids".
    Paddington 2's reads "wrongly convicted of theft... prison life", which sits
    semantically near crime films.

    The genre list IS that missing signal, but three words lose to a thirty-word
    synopsis once the model averages everything together. Repeating them raises
    their share of the result. Measured over the seed catalog, repeating three
    times took top-1 accuracy from 3/4 to 4/4 across plot and mood queries, with
    no loss on the plot queries.

    That is a small sample and weak evidence - four queries over thirty films.
    It is enough to prefer this over the alternative, not enough to call settled;
    the eval harness exists to test it properly against the full catalog. The
    cleaner long-term approach is embedding genres and synopsis separately and
    combining the scores, which costs a second column and is worth doing only if
    the eval says this is not good enough.
    """
    parts = [title.strip()]

    if genres:
        genre_text = ", ".join(genres)
        parts.extend([genre_text] * max(1, genre_repeat))

    if overview and overview.strip():
        parts.append(overview.strip())

    return ". ".join(part for part in parts if part)


def embed_texts(texts: Iterable[str], batch_size: int = 64) -> list[list[float]]:
    """Embed many texts at once.

    Batching matters: handing the model 64 texts together is far faster than 64
    separate calls, because the heavy matrix work happens once per batch instead
    of once per text.

    normalize_embeddings=True scales every vector to length 1. Cosine similarity
    only cares about direction, not magnitude, so normalising up front means the
    database compares directions directly and the numbers stay comparable across
    films of very different description lengths.
    """
    texts = list(texts)
    if not texts:
        return []

    vectors = get_model().encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return [vector.tolist() for vector in vectors]


def embed_query(text: str) -> list[float]:
    """Embed a single search query.

    Same model and same normalisation as the films. That is not optional - two
    vectors are only comparable if they came from the same model, so a query
    embedded by a different model would return meaningless neighbours.
    """
    return embed_texts([text])[0]
