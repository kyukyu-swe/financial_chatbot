"""
ChromaDB similarity search tool.

Searches the omise_docs collection and returns the top-k relevant chunks.
"""

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from ml.embeddings import embed_single  # noqa: E402
from vector_store.setup import get_collection  # noqa: E402

_DEFAULT_TOP_K = 3


def search_docs(query: str, top_k: int = _DEFAULT_TOP_K) -> list[dict]:
    """
    Embed *query* and return the top-*k* most similar Omise API doc chunks.

    Parameters
    ----------
    query:
        The user's natural-language question.
    top_k:
        Number of results to return (default 3).

    Returns
    -------
    list[dict]
        Each dict contains:
            - id (str): document ID
            - title (str): document title
            - topic (str): document topic category
            - content (str): document text
            - distance (float): cosine distance (lower = more similar)
    """
    collection = get_collection()
    query_embedding = embed_single(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    docs = []
    if not results or not results.get("ids"):
        return docs

    ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for doc_id, content, meta, dist in zip(ids, documents, metadatas, distances):
        docs.append(
            {
                "id": doc_id,
                "title": meta.get("title", ""),
                "topic": meta.get("topic", ""),
                "content": content,
                "distance": round(float(dist), 4),
            }
        )

    return docs
