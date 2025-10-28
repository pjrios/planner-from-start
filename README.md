# Planner Ingestion Service

This repository provides a local-first ingestion pipeline for class-planning materials. It
accepts documents via a FastAPI upload endpoint, chunks and embeds their contents using a
SentenceTransformer model, and stores the vectors in a persistent Chroma database for
semantic retrieval.

## Features
- Multi-file upload endpoint backed by FastAPI.
- Support for PDF, DOCX, PPTX, Markdown, and plain-text files.
- Sliding-window text chunking with configurable chunk size and overlap.
- SentenceTransformer embeddings with automatic CPU/MPS/CUDA device selection.
- Persistent local vector storage powered by ChromaDB.

## Quick start (macOS)
Run the setup script, which installs dependencies, downloads the embedding model, and
launches the API server:

```bash
./setup_mac.sh
```

Once the server is running, open another terminal and test the ingestion endpoint:

```bash
curl -X POST "http://localhost:8000/ingest" \
  -F "files=@/path/to/your/document.pdf" \
  -F "files=@/path/to/another.docx"
```

Check service health at `http://localhost:8000/health`.

## Windows instructions
See [WINDOWS_SETUP.md](WINDOWS_SETUP.md) for a step-by-step setup process tailored to
CUDA-enabled systems.

## Development tips
- The virtual environment is created at `.venv/`.
- Vector store artifacts live under `data/vector_store/` and are ignored by Git.
- Configure chunking and embedding behaviour with the environment variables documented in
  `backend/config.py` (e.g., `CHUNK_SIZE`, `CHUNK_OVERLAP`, `EMBEDDING_MODEL_NAME`).
