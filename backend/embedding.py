"""Embedding utilities using sentence-transformers."""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Iterable, List

import torch
from sentence_transformers import SentenceTransformer

from .config import EMBEDDING_MODEL_NAME

LOGGER = logging.getLogger(__name__)


def _infer_device() -> str:
    if torch.cuda.is_available():
        LOGGER.info("Using CUDA for embeddings")
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        LOGGER.info("Using Apple Metal (MPS) for embeddings")
        return "mps"
    LOGGER.info("Falling back to CPU for embeddings")
    return "cpu"


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """Load the embedding model once and reuse it."""
    device = _infer_device()
    model = SentenceTransformer(EMBEDDING_MODEL_NAME, device=device)
    LOGGER.info("Loaded embedding model '%s' on device '%s'", EMBEDDING_MODEL_NAME, device)
    return model


def embed_documents(chunks: Iterable[str]) -> List[List[float]]:
    model = get_embedding_model()
    embeddings = model.encode(list(chunks), convert_to_numpy=False, show_progress_bar=True)
    return [embedding.tolist() for embedding in embeddings]
