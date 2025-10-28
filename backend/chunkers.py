"""Utilities for chunking text into overlapping segments."""
from __future__ import annotations

from typing import Iterable, List


def sliding_window_chunk(text: str, *, chunk_size: int, overlap: int) -> List[str]:
    """Split ``text`` into overlapping chunks using a sliding window strategy."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap cannot be negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    words = text.split()
    if not words:
        return []

    chunks: List[str] = []
    start = 0
    step = chunk_size - overlap
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == len(words):
            break
        start += step
    return chunks


def chunk_documents(texts: Iterable[str], *, chunk_size: int, overlap: int) -> List[str]:
    """Chunk multiple documents and return a flat list of chunks."""
    chunks: List[str] = []
    for text in texts:
        chunks.extend(sliding_window_chunk(text, chunk_size=chunk_size, overlap=overlap))
    return chunks
