"""FastAPI application exposing ingestion endpoints."""
"""FastAPI application exposing ingestion and scheduling endpoints."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import FRONTEND_DIR, TEMP_UPLOAD_DIR
from .pipeline import ingest_files
from . import vector_store
from typing import Any, List

import mimetypes
from datetime import date, datetime

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from datetime import date, time
import sqlite3
from datetime import date
from typing import List

from datetime import datetime, timezone

from fastapi import FastAPI, File, HTTPException, UploadFile, Query
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pydantic import BaseModel, Field, validator

from .config import FRONTEND_DIR, TEMP_UPLOAD_DIR
from .database import get_db, init_db
from .pipeline import ingest_files
from .services import reports as reports_service
from .routes.ingest import router as plan_ingest_router
from . import vector_store
from .services import plan_review
from .database import init_db
from .routers import classes
from . import database, scheduler, vector_store

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Planner Ingestion Service", version="0.1.0")
mimetypes.add_type("application/javascript", ".jsx")

app = FastAPI(title="Planner Ingestion Service", version="0.1.0")
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
init_db()

app = FastAPI(title="Planner Ingestion Service", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(plan_ingest_router)


if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")
else:
    LOGGER.warning("Frontend directory %s not found", FRONTEND_DIR)


@app.on_event("startup")
def startup_event() -> None:
    database.init_db()


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
@app.on_event("startup")
def on_startup() -> None:
    """Ensure database tables exist when the application starts."""

    init_db()
class AcademicYearResponse(BaseModel):
    id: int
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
class ReschedulingSuggestion(BaseModel):
    id: int
    class_id: int
    holiday_id: int
    suggestion: str
    class_name: str | None = None
    scheduled_date: date | None = None


class HolidayBase(BaseModel):
    name: str = Field(..., min_length=1)
    start_date: date
    end_date: date
    academic_year_id: int

    @validator("end_date")
    def validate_date_range(cls, end_date: date, values: dict) -> date:  # noqa: N805
        start = values.get("start_date")
        if start and end_date < start:
            raise ValueError("end_date must be on or after start_date")
        return end_date


class HolidayCreate(HolidayBase):
    pass


class HolidayUpdate(HolidayBase):
    pass


class HolidayResponse(BaseModel):
    id: int
    name: str
    start_date: date
    end_date: date
    academic_year_id: int
    suggestions: list[ReschedulingSuggestion] = Field(default_factory=list)


class ClassResponse(BaseModel):
    id: int
    name: str
    scheduled_date: date
    academic_year_id: int
    suggestions: list[ReschedulingSuggestion] = Field(default_factory=list)


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
app.include_router(classes.router)
@app.get("/academic-years", response_model=list[AcademicYearResponse])
def list_academic_years() -> list[AcademicYearResponse]:
    with database.get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM academic_years ORDER BY DATE(start_date)"
        ).fetchall()
    return [AcademicYearResponse(**dict(row)) for row in rows]


@app.get("/classes", response_model=list[ClassResponse])
def list_classes(academic_year_id: int | None = None) -> list[ClassResponse]:
    with database.get_connection() as conn:
        query = "SELECT * FROM classes"
        params: tuple = ()
        if academic_year_id is not None:
            query += " WHERE academic_year_id = ?"
            params = (academic_year_id,)
        query += " ORDER BY DATE(scheduled_date)"
        rows = conn.execute(query, params).fetchall()
        class_ids = [row["id"] for row in rows]
        suggestions_lookup: dict[int, list[ReschedulingSuggestion]] = {id_: [] for id_ in class_ids}
        if class_ids:
            placeholders = ",".join(["?"] * len(class_ids))
            suggestion_rows = conn.execute(
                f"""
                SELECT rs.*, c.name AS class_name, c.scheduled_date
                FROM rescheduling_suggestions rs
                JOIN classes c ON c.id = rs.class_id
                WHERE rs.class_id IN ({placeholders})
                ORDER BY rs.id
                """,
                tuple(class_ids),
            ).fetchall()
            for row in suggestion_rows:
                suggestions_lookup[row["class_id"]].append(
                    ReschedulingSuggestion(**dict(row))
                )

        return [
            ClassResponse(
                id=row["id"],
                name=row["name"],
                scheduled_date=row["scheduled_date"],
                academic_year_id=row["academic_year_id"],
                suggestions=suggestions_lookup[row["id"]],
            )
            for row in rows
        ]


@app.get("/classes/{class_id}", response_model=ClassResponse)
def get_class(class_id: int) -> ClassResponse:
    with database.get_connection() as conn:
        return _load_class(conn, class_id)


@app.get("/holidays", response_model=list[HolidayResponse])
def list_holidays(academic_year_id: int | None = None) -> list[HolidayResponse]:
    with database.get_connection() as conn:
        query = "SELECT * FROM holidays"
        params: tuple = ()
        if academic_year_id is not None:
            query += " WHERE academic_year_id = ?"
            params = (academic_year_id,)
        query += " ORDER BY DATE(start_date)"
        rows = conn.execute(query, params).fetchall()

        responses = []
        for row in rows:
            suggestions_rows = conn.execute(
                """
                SELECT rs.*, c.name AS class_name, c.scheduled_date
                FROM rescheduling_suggestions rs
                JOIN classes c ON c.id = rs.class_id
                WHERE rs.holiday_id = ?
                ORDER BY rs.id
                """,
                (row["id"],),
            ).fetchall()

            responses.append(
                HolidayResponse(
                    id=row["id"],
                    name=row["name"],
                    start_date=row["start_date"],
                    end_date=row["end_date"],
                    academic_year_id=row["academic_year_id"],
                    suggestions=[ReschedulingSuggestion(**dict(item)) for item in suggestions_rows],
                )
            )
        return responses


@app.get("/holidays/{holiday_id}", response_model=HolidayResponse)
def get_holiday(holiday_id: int) -> HolidayResponse:
    with database.get_connection() as conn:
        holiday_row = conn.execute(
            "SELECT * FROM holidays WHERE id = ?", (holiday_id,)
        ).fetchone()
        if holiday_row is None:
            raise HTTPException(status_code=404, detail="Holiday not found")
        suggestions = conn.execute(
            """
            SELECT rs.*, c.name AS class_name, c.scheduled_date
            FROM rescheduling_suggestions rs
            JOIN classes c ON c.id = rs.class_id
            WHERE rs.holiday_id = ?
            ORDER BY rs.id
            """,
            (holiday_id,),
        ).fetchall()
        return HolidayResponse(
            id=holiday_row["id"],
            name=holiday_row["name"],
            start_date=holiday_row["start_date"],
            end_date=holiday_row["end_date"],
            academic_year_id=holiday_row["academic_year_id"],
            suggestions=[ReschedulingSuggestion(**dict(item)) for item in suggestions],
        )


@app.post("/holidays", response_model=HolidayResponse, status_code=201)
def create_holiday(payload: HolidayCreate) -> HolidayResponse:
    with database.get_connection() as conn:
        _ensure_academic_year(conn, payload.academic_year_id)
        cursor = conn.execute(
            """
            INSERT INTO holidays (name, start_date, end_date, academic_year_id)
            VALUES (?, ?, ?, ?)
            """,
            (
                payload.name,
                payload.start_date,
                payload.end_date,
                payload.academic_year_id,
            ),
        )
        holiday_id = cursor.lastrowid
        suggestions = scheduler.recompute_for_holiday(conn, holiday_id)
        holiday_row = conn.execute(
            "SELECT * FROM holidays WHERE id = ?", (holiday_id,)
        ).fetchone()
        return HolidayResponse(
            id=holiday_row["id"],
            name=holiday_row["name"],
            start_date=holiday_row["start_date"],
            end_date=holiday_row["end_date"],
            academic_year_id=holiday_row["academic_year_id"],
            suggestions=[ReschedulingSuggestion(**item) for item in suggestions],
        )


@app.put("/holidays/{holiday_id}", response_model=HolidayResponse)
def update_holiday(holiday_id: int, payload: HolidayUpdate) -> HolidayResponse:
    with database.get_connection() as conn:
        _ensure_academic_year(conn, payload.academic_year_id)
        existing = conn.execute(
            "SELECT id FROM holidays WHERE id = ?", (holiday_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Holiday not found")
        conn.execute(
            """
            UPDATE holidays
            SET name = ?, start_date = ?, end_date = ?, academic_year_id = ?
            WHERE id = ?
            """,
            (
                payload.name,
                payload.start_date,
                payload.end_date,
                payload.academic_year_id,
                holiday_id,
            ),
        )
        suggestions = scheduler.recompute_for_holiday(conn, holiday_id)
        holiday_row = conn.execute(
            "SELECT * FROM holidays WHERE id = ?", (holiday_id,)
        ).fetchone()
        return HolidayResponse(
            id=holiday_row["id"],
            name=holiday_row["name"],
            start_date=holiday_row["start_date"],
            end_date=holiday_row["end_date"],
            academic_year_id=holiday_row["academic_year_id"],
            suggestions=[ReschedulingSuggestion(**item) for item in suggestions],
        )


@app.delete("/holidays/{holiday_id}")
def delete_holiday(holiday_id: int) -> dict[str, str]:
    with database.get_connection() as conn:
        deleted = conn.execute(
            "DELETE FROM holidays WHERE id = ?", (holiday_id,)
        )
        if deleted.rowcount == 0:
            raise HTTPException(status_code=404, detail="Holiday not found")
    return {"status": "deleted"}


def _ensure_academic_year(conn, academic_year_id: int) -> None:
    year = conn.execute(
        "SELECT id FROM academic_years WHERE id = ?", (academic_year_id,)
    ).fetchone()
    if year is None:
        raise HTTPException(status_code=400, detail="Academic year not found")


def _load_class(conn, class_id: int) -> ClassResponse:
    class_row = conn.execute(
        "SELECT * FROM classes WHERE id = ?", (class_id,)
    ).fetchone()
    if class_row is None:
        raise HTTPException(status_code=404, detail="Class not found")

    suggestions_rows = conn.execute(
        """
        SELECT rs.*, c.name AS class_name, c.scheduled_date
        FROM rescheduling_suggestions rs
        JOIN classes c ON c.id = rs.class_id
        WHERE rs.class_id = ?
        ORDER BY rs.id
        """,
        (class_id,),
    ).fetchall()

    suggestions = [ReschedulingSuggestion(**dict(row)) for row in suggestions_rows]
    return ClassResponse(
        id=class_row["id"],
        name=class_row["name"],
        scheduled_date=class_row["scheduled_date"],
        academic_year_id=class_row["academic_year_id"],
        suggestions=suggestions,
    )
