"""
Local embedding helper using sentence-transformers/all-MiniLM-L6-v2.
The model is downloaded once and cached by the sentence-transformers library.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Union

from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    """Load (and cache) the embedding model. Thread-safe due to GIL + lru_cache."""
    return SentenceTransformer(MODEL_NAME)


def embed(text: Union[str, list[str]]) -> list[list[float]]:
    """
    Embed one or more texts.

    Parameters
    ----------
    text:
        A single string or a list of strings to embed.

    Returns
    -------
    list[list[float]]
        A list of embedding vectors (one per input string).
        Each vector has 384 dimensions.
    """
    model = _get_model()
    if isinstance(text, str):
        text = [text]
    embeddings = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
    return embeddings.tolist()


def embed_single(text: str) -> list[float]:
    """
    Convenience wrapper that embeds a single string and returns a flat vector.
    """
    return embed(text)[0]
