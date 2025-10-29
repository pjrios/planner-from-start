"""Application configuration settings."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Final

BASE_DIR: Final[Path] = Path(__file__).resolve().parent.parent
DATA_DIR: Final[Path] = BASE_DIR / "data"
VECTOR_DB_DIR: Final[Path] = DATA_DIR / "vector_store"
TEMP_UPLOAD_DIR: Final[Path] = DATA_DIR / "uploads"
FRONTEND_DIR: Final[Path] = BASE_DIR / "frontend"

# Default embedding model; can be overridden via environment variable.
EMBEDDING_MODEL_NAME: Final[str] = os.getenv(
    "EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"
)

# Default chunking parameters
CHUNK_SIZE: Final[int] = int(os.getenv("CHUNK_SIZE", 800))
CHUNK_OVERLAP: Final[int] = int(os.getenv("CHUNK_OVERLAP", 200))

# Ensure important directories exist at import time.
for directory in (DATA_DIR, VECTOR_DB_DIR, TEMP_UPLOAD_DIR):
    directory.mkdir(parents=True, exist_ok=True)
