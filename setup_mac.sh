#!/usr/bin/env bash
# Bootstrap the planner ingestion service on macOS and launch the API.
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This setup script is intended for macOS." >&2
  exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required but not found. Install it via Xcode command-line tools or Homebrew." >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "Creating Python virtual environment..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

python - <<'PY'
"""Warm up embedding model to avoid first-request latency."""
from sentence_transformers import SentenceTransformer
from backend.config import EMBEDDING_MODEL_NAME

print(f"Loading embedding model '{EMBEDDING_MODEL_NAME}'...", flush=True)
SentenceTransformer(EMBEDDING_MODEL_NAME)
print("Model ready.")
PY

export UVICORN_APP="backend.app:app"
export UVICORN_PORT="8000"

echo "Starting ingestion service on http://127.0.0.1:${UVICORN_PORT}"
exec uvicorn "${UVICORN_APP}" --host 0.0.0.0 --port "${UVICORN_PORT}"
