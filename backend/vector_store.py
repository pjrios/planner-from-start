"""Wrapper around Chroma vector store."""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List

LOGGER = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb import ClientAPI
    from chromadb.config import Settings
except Exception as exc:  # noqa: BLE001 - surface import errors at runtime
    chromadb = None  # type: ignore[assignment]
    ClientAPI = None  # type: ignore[assignment]
    Settings = None  # type: ignore[assignment]
    LOGGER.warning("ChromaDB could not be imported: %s", exc)

from .config import VECTOR_DB_DIR
_COLLECTION_NAME = "planner_documents"


def _get_client() -> ClientAPI:
    if chromadb is None or Settings is None:
        raise RuntimeError(
            "ChromaDB is not available. Install the chromadb extra dependencies to enable vector storage."
        )
    client = chromadb.PersistentClient(
        path=str(VECTOR_DB_DIR), settings=Settings(anonymized_telemetry=False)
    )
    return client


def get_or_create_collection():
    client = _get_client()
    return client.get_or_create_collection(_COLLECTION_NAME)


def add_embeddings(
    texts: List[str], embeddings: Iterable[List[float]], metadatas: List[dict[str, str]]
) -> None:
    try:
        collection = get_or_create_collection()
    except RuntimeError as exc:
        LOGGER.warning("Vector store unavailable; skipping embedding persistence: %s", exc)
        return
    existing_count = collection.count()
    ids = [f"doc_{existing_count + idx}" for idx in range(len(texts))]
    collection.add(
        ids=ids,
        documents=texts,
        embeddings=list(embeddings),
        metadatas=metadatas,
    )
    LOGGER.info("Persisted %s chunks to vector store", len(texts))


def similarity_search(query: str, *, n_results: int = 5) -> List[Dict[str, Any]]:
    try:
        collection = get_or_create_collection()
    except RuntimeError as exc:
        LOGGER.warning("Vector store unavailable; returning empty results: %s", exc)
        return []
    if collection.count() == 0:
        LOGGER.info("Similarity search skipped: collection is empty")
        return []

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    response: List[Dict[str, Any]] = []
    for doc, metadata, distance in zip(documents, metadatas, distances):
        response.append(
            {
                "document": doc,
                "metadata": metadata or {},
                "distance": distance,
            }
        )

    return response
