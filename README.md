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
- Built-in web interface for uploading documents and running semantic searches with
  provenance metadata.

## Quick start (macOS)
Run the setup script, which installs dependencies, downloads the embedding model, and
launches the API server:

```bash
./setup_mac.sh
```

Once the server is running, visit <http://localhost:8000> to open the web interface.
Use the **Upload materials** panel to ingest files and the **Search your knowledge
base** panel to query the stored chunks. Each result shows the original file name,
chunk index, and similarity score so you can trace every answer back to its source.

You can still interact with the API directly:

```bash
curl -X POST "http://localhost:8000/ingest" \
  -F "files=@/path/to/your/document.pdf" \
  -F "files=@/path/to/another.docx"

curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "assessment rubric", "n_results": 3}'
```

Check service health at `http://localhost:8000/health`.

### Troubleshooting
- If `uvicorn` crashes with `AttributeError: np.float_ was removed in the NumPy 2.0 release`,
  reinstall the requirements to ensure the pinned NumPy < 2.0 version is used:
  ```bash
  source .venv/bin/activate
  pip install --upgrade --force-reinstall -r requirements.txt
  ```

## Windows instructions
See [WINDOWS_SETUP.md](WINDOWS_SETUP.md) for a step-by-step setup process tailored to
CUDA-enabled systems.

## Development tips
- The virtual environment is created at `.venv/`.
- Vector store artifacts live under `data/vector_store/` and are ignored by Git.
- Configure chunking and embedding behaviour with the environment variables documented in
  `backend/config.py` (e.g., `CHUNK_SIZE`, `CHUNK_OVERLAP`, `EMBEDDING_MODEL_NAME`).
