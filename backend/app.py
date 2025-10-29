"""FastAPI application exposing ingestion endpoints."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from datetime import datetime, timezone

from fastapi import FastAPI, File, HTTPException, UploadFile, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import FRONTEND_DIR, TEMP_UPLOAD_DIR
from .pipeline import ingest_files
from .services import reports as reports_service
from . import vector_store

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Planner Ingestion Service", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")
else:
    LOGGER.warning("Frontend directory %s not found", FRONTEND_DIR)


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    n_results: int = Field(5, ge=1, le=50)


class QueryResult(BaseModel):
    document: str
    metadata: dict[str, str]
    distance: float | None = None


class QueryResponse(BaseModel):
    query: str
    results: list[QueryResult]


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def serve_frontend() -> FileResponse:
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend assets not found")
    return FileResponse(index_path)


@app.post("/ingest")
async def ingest_endpoint(files: List[UploadFile] = File(...)) -> dict[str, int]:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    temp_paths: List[Path] = []
    try:
        for upload in files:
            destination = TEMP_UPLOAD_DIR / upload.filename
            with destination.open("wb") as buffer:
                buffer.write(await upload.read())
            temp_paths.append(destination)
            LOGGER.info("Saved upload %s", destination)

        result = ingest_files(temp_paths)
    except Exception as exc:  # noqa: BLE001 - convert to HTTP error
        LOGGER.exception("Ingestion failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        for path in temp_paths:
            if path.exists():
                path.unlink()
    return result


@app.post("/query", response_model=QueryResponse)
def query_endpoint(payload: QueryRequest) -> QueryResponse:
    results = vector_store.similarity_search(
        payload.query, n_results=payload.n_results
    )
    return QueryResponse(
        query=payload.query,
        results=[QueryResult(**item) for item in results],
    )


def _report_response(
    format_: str | None,
    filename: str,
    summary: list[dict],
    csv_builder,
    pdf_builder,
):
    if format_ is None:
        return JSONResponse(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "rows": summary,
            }
        )

    format_lower = format_.lower()
    if format_lower == "csv":
        csv_data = csv_builder(summary).encode("utf-8")
        return StreamingResponse(
            iter([csv_data]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}.csv",
            },
        )
    if format_lower == "pdf":
        pdf_data = pdf_builder(summary)
        return StreamingResponse(
            iter([pdf_data]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}.pdf",
            },
        )

    raise HTTPException(status_code=400, detail="Unsupported format. Use csv or pdf.")


@app.get("/reports/trimester")
def get_trimester_report(format: str | None = Query(default=None)):
    summary = reports_service.trimester_summary()
    return _report_response(
        format,
        "trimester_report",
        summary,
        reports_service.build_trimester_csv,
        reports_service.build_trimester_pdf,
    )


@app.get("/reports/topic")
def get_topic_report(format: str | None = Query(default=None)):
    summary = reports_service.topic_summary()
    return _report_response(
        format,
        "topic_report",
        summary,
        reports_service.build_topic_csv,
        reports_service.build_topic_pdf,
    )
