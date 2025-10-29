"""FastAPI application exposing ingestion endpoints."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List

import mimetypes
from datetime import date, datetime

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import FRONTEND_DIR, TEMP_UPLOAD_DIR
from .pipeline import ingest_files
from . import vector_store
from .services import plan_review

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

mimetypes.add_type("application/javascript", ".jsx")

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


class PlanAuditEntry(BaseModel):
    timestamp: datetime
    action: str
    payload: dict[str, Any] | None = None


class Trimester(BaseModel):
    id: str
    name: str
    start_date: date
    end_date: date


class Level(BaseModel):
    id: str
    name: str
    description: str | None = None


class Topic(BaseModel):
    id: str
    name: str
    trimester_id: str
    level_id: str
    summary: str | None = None


class PlanDraft(BaseModel):
    id: str
    title: str
    summary: str | None = None
    status: str
    review_notes: str | None = None
    trimesters: list[Trimester]
    levels: list[Level]
    topics: list[Topic]
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None = None
    history: list[PlanAuditEntry] = Field(default_factory=list)


class PlanPatchRequest(BaseModel):
    title: str | None = None
    summary: str | None = None
    status: str | None = None
    review_notes: str | None = None
    trimesters: list[Trimester] | None = None
    levels: list[Level] | None = None
    topics: list[Topic] | None = None


class ReviewActionRequest(BaseModel):
    review_notes: str | None = None


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


@app.get("/plans/{draft_id}", response_model=PlanDraft)
def get_plan_draft(draft_id: str) -> PlanDraft:
    data = plan_review.get_draft(draft_id)
    return PlanDraft(**data)


@app.patch("/plans/{draft_id}", response_model=PlanDraft)
def patch_plan_draft(draft_id: str, payload: PlanPatchRequest) -> PlanDraft:
    changes = jsonable_encoder(payload, exclude_unset=True)
    data = plan_review.patch_draft(draft_id, changes)
    return PlanDraft(**data)


@app.post("/plans/{draft_id}/approve", response_model=PlanDraft)
def approve_plan_draft(
    draft_id: str,
    payload: ReviewActionRequest = Body(default=ReviewActionRequest()),
) -> PlanDraft:
    changes = jsonable_encoder(payload, exclude_unset=True)
    data = plan_review.approve_draft(draft_id, changes)
    return PlanDraft(**data)


@app.post("/plans/{draft_id}/reparse", response_model=PlanDraft)
def reparse_plan_draft(
    draft_id: str,
    payload: ReviewActionRequest = Body(default=ReviewActionRequest()),
) -> PlanDraft:
    changes = jsonable_encoder(payload, exclude_unset=True)
    data = plan_review.request_reparse(draft_id, changes)
    return PlanDraft(**data)
