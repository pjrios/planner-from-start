"""Document ingestion pipeline utilities."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, List

from . import chunkers, document_loaders, embedding, vector_store
from .config import CHUNK_OVERLAP, CHUNK_SIZE

LOGGER = logging.getLogger(__name__)


def ingest_files(file_paths: Iterable[Path]) -> dict[str, int]:
    """Ingest provided files into the vector store."""
    provided_files = list(Path(path) for path in file_paths)
    supported_files = list(document_loaders.iter_supported_files(provided_files))
    unsupported_count = len(provided_files) - len(supported_files)
    if unsupported_count:
        LOGGER.warning(
            "%s files skipped due to unsupported extensions", unsupported_count
        )

    if not supported_files:
        raise ValueError("No supported files provided for ingestion.")

    documents: List[str] = []
    metadatas: List[dict[str, str]] = []
    skipped_files = 0

    for path in supported_files:
        LOGGER.info("Loading %s", path)
        text = document_loaders.load_document(path)
        if text.strip():
            documents.append(text)
            metadatas.append({"source": str(path)})
        else:
            skipped_files += 1
            LOGGER.warning("Skipping empty document %s", path)

    chunks: List[str] = []
    chunk_metadatas: List[dict[str, str]] = []

    for doc_index, (text, metadata) in enumerate(zip(documents, metadatas)):
        doc_chunks = chunkers.sliding_window_chunk(
            text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP
        )
        for chunk_index, chunk in enumerate(doc_chunks):
            chunk_metadata = metadata.copy()
            chunk_metadata["chunk_index"] = str(chunk_index)
            chunk_metadata["document_index"] = str(doc_index)
            chunks.append(chunk)
            chunk_metadatas.append(chunk_metadata)

    LOGGER.info(
        "Created %s chunks from %s documents", len(chunks), len(documents)
    )

    if not chunks:
        raise ValueError("No text extracted from the provided files.")

    embeddings = embedding.embed_documents(chunks)
    vector_store.add_embeddings(chunks, embeddings, chunk_metadatas)
    return {
        "documents_ingested": len(documents),
        "chunks_created": len(chunks),
        "unsupported_files": unsupported_count,
        "empty_documents": skipped_files,
    }
