"""FastAPI application exposing ingestion and scheduling endpoints."""
from __future__ import annotations

import logging
from pathlib import Path
from datetime import date, time
import sqlite3
from typing import List

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .config import FRONTEND_DIR, TEMP_UPLOAD_DIR
from .database import get_db, init_db
from .pipeline import ingest_files

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

try:  # pragma: no cover - chromadb may be unavailable in test environments
    from . import vector_store
except Exception as exc:  # noqa: BLE001 - log and continue without vector store
    vector_store = None
    LOGGER.warning("Vector store unavailable: %s", exc)
from .schemas import (
    AgendaResponse,
    ClassResponse,
    ClassUpdate,
    GroupCreate,
    GroupResponse,
    GroupSummary,
    LevelCreate,
    LevelResponse,
    PlanPayload,
    ScheduleSlotResponse,
)
from .services.scheduler import SchedulerError, generate_classes

app = FastAPI(title="Planner Ingestion Service", version="0.2.0")
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


@app.on_event("startup")
def on_startup() -> None:
    """Ensure database tables exist when the application starts."""

    init_db()


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
    if vector_store is None:
        raise HTTPException(status_code=503, detail="Vector store unavailable")
    results = vector_store.similarity_search(
        payload.query, n_results=payload.n_results
    )
    return QueryResponse(
        query=payload.query,
        results=[QueryResult(**item) for item in results],
    )


def _row_to_level(row: sqlite3.Row) -> LevelResponse:
    return LevelResponse(
        id=row["id"],
        name=row["name"],
        start_date=date.fromisoformat(row["start_date"]),
    )


def _row_to_schedule(row: sqlite3.Row) -> ScheduleSlotResponse:
    end_time_value = row["end_time"]
    return ScheduleSlotResponse(
        id=row["id"],
        weekday=row["weekday"],
        start_time=time.fromisoformat(row["start_time"]),
        end_time=time.fromisoformat(end_time_value) if end_time_value else None,
    )


def _row_to_class_response(row: sqlite3.Row, group_name: str) -> ClassResponse:
    end_time_value = row["end_time"]
    return ClassResponse(
        id=row["id"],
        group=GroupSummary(id=row["group_id"], name=group_name),
        week_number=row["week_number"],
        date=date.fromisoformat(row["date"]),
        start_time=time.fromisoformat(row["start_time"]),
        end_time=time.fromisoformat(end_time_value) if end_time_value else None,
        topic=row["topic"],
        trimester_color=row["trimester_color"],
        status=row["status"],
        manual_override=bool(row["manual_override"]),
    )


@app.post("/levels", response_model=LevelResponse, status_code=status.HTTP_201_CREATED)
def create_level(payload: LevelCreate, db: sqlite3.Connection = Depends(get_db)) -> LevelResponse:
    cursor = db.execute(
        "INSERT INTO levels (name, start_date) VALUES (?, ?)",
        (payload.name, payload.start_date.isoformat()),
    )
    level_id = cursor.lastrowid
    row = db.execute("SELECT id, name, start_date FROM levels WHERE id = ?", (level_id,)).fetchone()
    assert row is not None
    return _row_to_level(row)


@app.post(
    "/levels/{level_id}/groups",
    response_model=GroupResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_group(
    level_id: int, payload: GroupCreate, db: sqlite3.Connection = Depends(get_db)
) -> GroupResponse:
    level_row = db.execute("SELECT id FROM levels WHERE id = ?", (level_id,)).fetchone()
    if level_row is None:
        raise HTTPException(status_code=404, detail="Level not found")

    cursor = db.execute(
        "INSERT INTO groups (level_id, name) VALUES (?, ?)",
        (level_id, payload.name),
    )
    group_id = cursor.lastrowid

    for slot in payload.schedule:
        db.execute(
            "INSERT INTO schedules (group_id, weekday, start_time, end_time) VALUES (?, ?, ?, ?)",
            (
                group_id,
                slot.weekday,
                slot.start_time.isoformat(),
                slot.end_time.isoformat() if slot.end_time else None,
            ),
        )

    schedule_rows = db.execute(
        "SELECT id, weekday, start_time, end_time FROM schedules WHERE group_id = ? ORDER BY weekday, start_time",
        (group_id,),
    ).fetchall()
    schedule = [_row_to_schedule(row) for row in schedule_rows]

    return GroupResponse(id=group_id, name=payload.name, level_id=level_id, schedule=schedule)


@app.post(
    "/levels/{level_id}/generate-classes",
    status_code=status.HTTP_201_CREATED,
)
def generate_classes_endpoint(
    level_id: int, payload: PlanPayload, db: sqlite3.Connection = Depends(get_db)
) -> dict[str, int]:
    if payload.level_id != level_id:
        raise HTTPException(status_code=400, detail="level_id does not match path")

    try:
        generated = generate_classes(payload, db)
    except SchedulerError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"generated": len(generated)}


@app.patch("/classes/{class_id}", response_model=ClassResponse)
def update_class(
    class_id: int, payload: ClassUpdate, db: sqlite3.Connection = Depends(get_db)
) -> ClassResponse:
    try:
        payload.ensure_any_field()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    row = db.execute(
        "SELECT id, group_id, week_number, date, start_time, end_time, topic, trimester_color, status, manual_override FROM classes WHERE id = ?",
        (class_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Class not found")

    changed = False
    updates: dict[str, object] = {}

    if payload.date is not None and payload.date.isoformat() != row["date"]:
        updates["date"] = payload.date.isoformat()
        changed = True
    if payload.start_time is not None and payload.start_time.isoformat() != row["start_time"]:
        updates["start_time"] = payload.start_time.isoformat()
        changed = True
    fields_set = payload.model_fields_set

    if payload.end_time is not None:
        end_iso = payload.end_time.isoformat()
        if end_iso != (row["end_time"] or None):
            updates["end_time"] = end_iso
            changed = True
    if payload.end_time is None and row["end_time"] is not None and "end_time" in fields_set:
        updates["end_time"] = None
        changed = True
    if payload.week_number is not None and payload.week_number != row["week_number"]:
        updates["week_number"] = payload.week_number
        changed = True
    if payload.topic is not None and payload.topic != row["topic"]:
        updates["topic"] = payload.topic
        changed = True
    if (
        payload.trimester_color is not None
        and payload.trimester_color != row["trimester_color"]
    ):
        updates["trimester_color"] = payload.trimester_color
        changed = True
    if payload.status is not None:
        updates["status"] = payload.status
    elif changed:
        updates["status"] = "rescheduled"

    if changed or payload.status is not None:
        updates["manual_override"] = 1

    if updates:
        set_clause = ", ".join(f"{column} = ?" for column in updates)
        values = list(updates.values())
        values.append(class_id)
        db.execute(f"UPDATE classes SET {set_clause} WHERE id = ?", values)

    updated_row = db.execute(
        "SELECT id, group_id, week_number, date, start_time, end_time, topic, trimester_color, status, manual_override FROM classes WHERE id = ?",
        (class_id,),
    ).fetchone()
    assert updated_row is not None

    group_row = db.execute(
        "SELECT name FROM groups WHERE id = ?",
        (updated_row["group_id"],),
    ).fetchone()
    group_name = group_row["name"] if group_row else ""

    return _row_to_class_response(updated_row, group_name)


@app.get("/agenda", response_model=AgendaResponse)
def agenda_endpoint(
    level_id: int, week: int, db: sqlite3.Connection = Depends(get_db)
) -> AgendaResponse:
    if week <= 0:
        raise HTTPException(status_code=400, detail="week must be greater than zero")

    level_row = db.execute("SELECT id FROM levels WHERE id = ?", (level_id,)).fetchone()
    if level_row is None:
        raise HTTPException(status_code=404, detail="Level not found")

    rows = db.execute(
        """
        SELECT classes.id, classes.group_id, classes.week_number, classes.date, classes.start_time,
               classes.end_time, classes.topic, classes.trimester_color, classes.status, classes.manual_override,
               groups.name AS group_name
        FROM classes
        JOIN groups ON classes.group_id = groups.id
        WHERE groups.level_id = ? AND classes.week_number = ?
        ORDER BY classes.date, classes.start_time
        """,
        (level_id, week),
    ).fetchall()

    class_payload = [_row_to_class_response(row, row["group_name"]) for row in rows]

    return AgendaResponse(level_id=level_id, week=week, classes=class_payload)
