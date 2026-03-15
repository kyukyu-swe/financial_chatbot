"""
ChromaDB vector store setup.

Run once (idempotent) to embed and persist the Omise fake docs.
Persists the collection to ./chroma_db/ relative to the project root.
"""

from __future__ import annotations

import os
import sys

import chromadb

# Allow running this module directly from the project root
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from docs.fake_docs import OMISE_DOCS  # noqa: E402
from ml.embeddings import embed  # noqa: E402

CHROMA_DIR = os.path.join(_PROJECT_ROOT, "chroma_db")
COLLECTION_NAME = "omise_docs"


def get_chroma_client() -> chromadb.PersistentClient:
    """Return a persistent ChromaDB client pointed at CHROMA_DIR."""
    return chromadb.PersistentClient(path=CHROMA_DIR)


def setup_vector_store(force: bool = False) -> chromadb.Collection:
    """
    Create (or load) the omise_docs collection and populate it with
    embeddings from OMISE_DOCS.

    Parameters
    ----------
    force:
        If True, delete the existing collection before re-creating it.
        Defaults to False (idempotent — skips if already populated).

    Returns
    -------
    chromadb.Collection
        The populated collection.
    """
    client = get_chroma_client()

    if force:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    existing_count = collection.count()
    if existing_count >= len(OMISE_DOCS):
        print(
            f"[vector_store] Collection '{COLLECTION_NAME}' already has "
            f"{existing_count} documents — skipping ingestion."
        )
        return collection

    texts = [doc["content"] for doc in OMISE_DOCS]
    embeddings = embed(texts)

    collection.add(
        ids=[doc["id"] for doc in OMISE_DOCS],
        embeddings=embeddings,
        documents=[doc["content"] for doc in OMISE_DOCS],
        metadatas=[
            {"title": doc["title"], "topic": doc["topic"]} for doc in OMISE_DOCS
        ],
    )

    print(
        f"[vector_store] Ingested {len(OMISE_DOCS)} documents into "
        f"collection '{COLLECTION_NAME}'."
    )
    return collection


def get_collection() -> chromadb.Collection:
    """
    Return the omise_docs collection, initialising it if necessary.
    Suitable for use at application startup.
    """
    return setup_vector_store(force=False)


if __name__ == "__main__":
    setup_vector_store(force="--force" in sys.argv)
    print("[vector_store] Setup complete.")
