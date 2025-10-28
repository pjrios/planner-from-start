# Windows Setup Guide

This guide prepares a Windows 10/11 machine with an NVIDIA GeForce RTX 3050 (4 GB VRAM) for running the planner ingestion and embedding service entirely offline. The instructions assume you are using a local administrator account.

## 1. Install System Prerequisites

1. **Windows Updates** – Install all available updates and reboot.
2. **GPU Drivers** – Install the latest [NVIDIA Game Ready or Studio Driver](https://www.nvidia.com/Download/index.aspx). Reboot after installation.
3. **Python 3.11 (64-bit)** – Download from [python.org](https://www.python.org/downloads/windows/) and enable:
   - "Add python.exe to PATH"
   - "Install launcher for all users"
4. **Git for Windows** – Download from [git-scm.com](https://git-scm.com/download/win) using default settings.
5. **Microsoft Visual C++ Build Tools** – Install from [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/).
   - Workloads: `Desktop development with C++`
   - Individual components: `MSVC v143`, `Windows 11 SDK` (or Windows 10 SDK if applicable).
6. **(Optional) Windows Terminal** – Available from the Microsoft Store for an improved shell.

## 2. Prepare the Project Workspace

1. Open **PowerShell** (or Windows Terminal) as Administrator.
2. Create a workspace folder and clone the repository:
   ```powershell
   cd $env:USERPROFILE
   mkdir planner-from-start
   cd planner-from-start
   git clone https://github.com/<your-account>/planner-from-start.git .
   ```
3. Verify Git is configured:
   ```powershell
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
   ```

## 3. Create and Activate a Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

If PowerShell blocks script execution, run:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
Then reactivate the environment.

## 4. Install CUDA-Enabled PyTorch

1. Check CUDA capability of your GPU:
   ```powershell
   nvidia-smi
   ```
2. Install PyTorch with CUDA 12.1 wheels (supported on RTX 3050):
   ```powershell
   pip install --index-url https://download.pytorch.org/whl/cu121 torch torchvision torchaudio
   ```
3. Confirm PyTorch sees the GPU:
   ```powershell
   python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
   ```
   The command should output `True` and `NVIDIA GeForce RTX 3050`.

## 5. Install Project Dependencies

Install document loaders, chunkers, embedding models, and vector database clients:
```powershell
pip install --upgrade \
    fastapi uvicorn[standard] pydantic \
    python-multipart tqdm rich \
    sentence-transformers "transformers>=4.38" accelerate \
    chromadb qdrant-client \
    unstructured[all-docs] pdfminer.six pypdf \
    llama-cpp-python==0.2.79 "ctranslate2<4" \
    torchmetrics scikit-learn
```

### Optional Enhancements
- **GPU-accelerated OCR** (if you expect scanned PDFs):
  ```powershell
  pip install easyocr opencv-python-headless
  ```
- **LangChain tooling** (for pipelines and evaluations):
  ```powershell
  pip install langchain langchain-community
  ```

## 6. Install and Configure a Vector Database

### Option A – ChromaDB (embedded, simplest)
1. No extra install required beyond the `chromadb` package.
2. Configure persistence directory in your FastAPI settings (e.g., `.\data\chroma`).

### Option B – Qdrant (local service with REST API)
1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and enable WSL 2 backend.
2. Start Qdrant in a PowerShell window:
   ```powershell
   docker run --name qdrant -p 6333:6333 -v ${PWD}\qdrant_data:/qdrant/storage qdrant/qdrant
   ```
3. Verify the service:
   ```powershell
   Invoke-WebRequest http://localhost:6333/health -UseBasicParsing
   ```

## 7. Configure Environment Variables

Create a `.env` file in the project root to store configuration values:
```ini
# .env
APP_HOST=0.0.0.0
APP_PORT=8000
VECTOR_DB=chroma        # or qdrant
CHROMA_PERSIST_DIR=./data/chroma
EMBEDDING_MODEL=intfloat/e5-small-v2
CHUNK_SIZE=750
CHUNK_OVERLAP=150
```

For Qdrant, add:
```ini
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

## 8. Initialize Local Directories

```powershell
mkdir data
mkdir data\uploads
mkdir data\chroma
```

## 9. Run the Ingestion & Embedding Service

1. Ensure the virtual environment is active.
2. Launch the FastAPI backend:
   ```powershell
   uvicorn backend.ingest_service:app --host 0.0.0.0 --port 8000 --reload
   ```
3. Open another PowerShell window (with the virtual environment activated) to run ingestion tests.

### Smoke Test – Upload a Sample Document
```powershell
Invoke-WebRequest `
  -Uri http://localhost:8000/upload `
  -Method Post `
  -InFile .\samples\lesson-plan.pdf `
  -Headers @{"Content-Type" = "application/pdf"}
```
Check the backend logs for successful preprocessing and embedding writes.

## 10. GPU Utilization Tips

- Monitor GPU load while ingesting documents:
  ```powershell
  nvidia-smi --loop=1
  ```
- If you experience CUDA out-of-memory errors:
  - Reduce batch size in your embedding configuration.
  - Switch to a smaller model (e.g., `sentence-transformers/all-MiniLM-L6-v2`).
  - Consider quantized models via `llama-cpp-python` and adjust context window.

## 11. Keeping Dependencies Updated

Periodically update packages inside the virtual environment:
```powershell
pip list --outdated
pip install --upgrade <package-name>
```

For PyTorch/CUDA updates, follow release notes to ensure compatibility with your GPU driver.

## 12. Troubleshooting

| Symptom | Possible Cause | Fix |
| --- | --- | --- |
| `python` command not found | PATH not updated | Reinstall Python and select "Add to PATH" or add `C:\Users\<you>\AppData\Local\Programs\Python\Python311\` to PATH manually. |
| `torch.cuda.is_available()` returns `False` | Incorrect PyTorch build or driver issue | Reinstall PyTorch using the CUDA wheel; update NVIDIA drivers. |
| `pip install` fails with build errors | Missing VC++ build tools | Re-run Visual Studio Build Tools installer and ensure C++ workload is installed. |
| Docker cannot start Qdrant | WSL 2 disabled | Enable WSL 2 via `wsl --install` and reboot. |

## 13. Next Steps

With the environment ready, proceed to:
1. Implement or update `backend/ingest_service.py` with file upload routes.
2. Configure chunking/embedding modules to read `.env` settings.
3. Begin ingesting class plans and verifying retrieval workflows.

Keep this guide alongside the repository for future reference and onboarding.
