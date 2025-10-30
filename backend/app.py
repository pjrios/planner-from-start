"""FastAPI application exposing ingestion and scheduling endpoints."""
from __future__ import annotations

import logging
import mimetypes
import sqlite3
from contextlib import suppress
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, List

from fastapi import (
    Body,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import database, scheduler
from .config import FRONTEND_DIR, TEMP_UPLOAD_DIR
from .database import get_db, init_db
from .pipeline import ingest_files
from .routes.ingest import router as plan_ingest_router
from .routers import classes as classes_router
from .schemas import (
    AcademicYearResponse,
    AgendaResponse,
    ClassResponse,
    ClassUpdate,
    GroupCreate,
    GroupResponse,
    GroupSummary,
    HolidayCreate,
    HolidayResponse,
    HolidayUpdate,
    LevelCreate,
    LevelResponse,
    PlanDraft,
    PlanPatchRequest,
    PlanPayload,
    QueryRequest,
    QueryResponse,
    QueryResult,
    ReschedulingSuggestion,
    ReviewActionRequest,
    ScheduleSlotResponse,
)
from .services import plan_review, reports as reports_service
from .services.scheduler import SchedulerError, generate_classes

LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

mimetypes.add_type("application/javascript", ".jsx")

app = FastAPI(title="Planner Ingestion Service", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:  # pragma: no cover - optional dependency
    from . import vector_store  # type: ignore
except Exception as exc:  # noqa: BLE001 - degrade gracefully
    vector_store = None  # type: ignore[assignment]
    LOGGER.warning("Vector store unavailable: %s", exc)

app.include_router(plan_ingest_router)
app.include_router(classes_router.router)

if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")
else:  # pragma: no cover - warn in dev environments
    LOGGER.warning("Frontend directory %s not found", FRONTEND_DIR)


@app.on_event("startup")
def startup_event() -> None:  # pragma: no cover - exercised indirectly
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
        raise HTTPException(status_code=400, detail="No files provided")

    TEMP_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_paths: list[Path] = []
    try:
        for upload in files:
            destination = TEMP_UPLOAD_DIR / upload.filename
            with destination.open("wb") as buffer:
                buffer.write(await upload.read())
            stored_paths.append(destination)
            LOGGER.info("Stored upload at %s", destination)

        result = ingest_files(stored_paths)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - return consistent error to clients
        LOGGER.exception("Ingestion failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        for path in stored_paths:
            with suppress(FileNotFoundError):
                path.unlink()
    return result


@app.post("/query", response_model=QueryResponse)
def query_endpoint(payload: QueryRequest) -> QueryResponse:
    if vector_store is None:
        raise HTTPException(status_code=503, detail="Vector store unavailable")
    results = vector_store.similarity_search(  # type: ignore[union-attr]
        payload.query, n_results=payload.n_results
    )
    return QueryResponse(
        query=payload.query,
        results=[QueryResult(**item) for item in results],
    )


def _report_response(
    format_: str | None,
    filename: str,
    summary: list[dict[str, Any]],
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
            headers={"Content-Disposition": f"attachment; filename={filename}.csv"},
        )
    if format_lower == "pdf":
        pdf_data = pdf_builder(summary)
        return StreamingResponse(
            iter([pdf_data]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}.pdf"},
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


# ---------------------------------------------------------------------------
# Scheduling helpers used by multiple endpoints and tests
# ---------------------------------------------------------------------------


def _row_to_level(row: sqlite3.Row) -> LevelResponse:
    return LevelResponse(
        id=row["id"],
        name=row["name"],
        start_date=date.fromisoformat(row["start_date"]),
    )


def _row_to_schedule(row: sqlite3.Row) -> ScheduleSlotResponse:
    end_value = row["end_time"]
    return ScheduleSlotResponse(
        id=row["id"],
        weekday=row["weekday"],
        start_time=time.fromisoformat(row["start_time"]),
        end_time=time.fromisoformat(end_value) if end_value else None,
    )


def _row_to_class_response(row: sqlite3.Row, group_name: str) -> ClassResponse:
    end_value = row["end_time"]
    return ClassResponse(
        id=row["id"],
        group=GroupSummary(id=row["group_id"], name=group_name),
        week_number=row["week_number"],
        date=date.fromisoformat(row["date"]),
        start_time=time.fromisoformat(row["start_time"]),
        end_time=time.fromisoformat(end_value) if end_value else None,
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
    row = db.execute(
        "SELECT id, name, start_date FROM levels WHERE id = ?",
        (level_id,),
    ).fetchone()
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
        "SELECT * FROM classes WHERE id = ?",
        (class_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Class not found")

    updates: dict[str, object | None] = {}
    changed = False

    if payload.date is not None and payload.date.isoformat() != row["date"]:
        updates["date"] = payload.date.isoformat()
        changed = True
    if payload.start_time is not None and payload.start_time.isoformat() != row["start_time"]:
        updates["start_time"] = payload.start_time.isoformat()
        changed = True
    if "end_time" in payload.model_fields_set:
        if payload.end_time is None:
            if row["end_time"] is not None:
                updates["end_time"] = None
                changed = True
        else:
            end_iso = payload.end_time.isoformat()
            if end_iso != (row["end_time"] or None):
                updates["end_time"] = end_iso
                changed = True
    if payload.week_number is not None and payload.week_number != row["week_number"]:
        updates["week_number"] = payload.week_number
        changed = True
    if payload.topic is not None and payload.topic != row["topic"]:
        updates["topic"] = payload.topic
        changed = True
    if payload.trimester_color is not None and payload.trimester_color != row["trimester_color"]:
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
        "SELECT * FROM classes WHERE id = ?",
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


@app.get("/academic-years", response_model=list[AcademicYearResponse])
def list_academic_years() -> list[AcademicYearResponse]:
    with database.connection_scope() as conn:
        rows = conn.execute(
            "SELECT * FROM academic_years ORDER BY DATE(start_date)"
        ).fetchall()
    return [AcademicYearResponse(**dict(row)) for row in rows]


@app.get("/classes", response_model=list[ClassResponse])
def list_classes(academic_year_id: int | None = None) -> list[ClassResponse]:
    with database.connection_scope() as conn:
        query = "SELECT * FROM classes"
        params: tuple = ()
        if academic_year_id is not None:
            query += " WHERE academic_year_id = ?"
            params = (academic_year_id,)
        query += " ORDER BY DATE(date)"
        rows = conn.execute(query, params).fetchall()
        class_ids = [row["id"] for row in rows]
        suggestions_lookup: dict[int, list[ReschedulingSuggestion]] = {id_: [] for id_ in class_ids}
        if class_ids:
            placeholders = ",".join("?" for _ in class_ids)
            suggestion_rows = conn.execute(
                f"""
                SELECT rs.*, c.name AS class_name, c.date AS scheduled_date
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

        responses = []
        for row in rows:
            group_row = conn.execute(
                "SELECT name FROM groups WHERE id = ?",
                (row["group_id"],),
            ).fetchone()
            group_name = group_row["name"] if group_row else ""
            responses.append(
                _row_to_class_response(row, group_name).model_copy(
                    update={"suggestions": suggestions_lookup[row["id"]]}
                )
            )
        return responses


@app.get("/classes/{class_id}", response_model=ClassResponse)
def get_class(class_id: int) -> ClassResponse:
    with database.connection_scope() as conn:
        return _load_class(conn, class_id)


@app.get("/holidays", response_model=list[HolidayResponse])
def list_holidays(academic_year_id: int | None = None) -> list[HolidayResponse]:
    with database.connection_scope() as conn:
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
                SELECT rs.*, c.name AS class_name, c.date AS scheduled_date
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
                    start_date=date.fromisoformat(row["start_date"]),
                    end_date=date.fromisoformat(row["end_date"]),
                    academic_year_id=row["academic_year_id"],
                    suggestions=[ReschedulingSuggestion(**dict(item)) for item in suggestions_rows],
                )
            )
        return responses


@app.get("/holidays/{holiday_id}", response_model=HolidayResponse)
def get_holiday(holiday_id: int) -> HolidayResponse:
    with database.connection_scope() as conn:
        holiday_row = conn.execute(
            "SELECT * FROM holidays WHERE id = ?", (holiday_id,)
        ).fetchone()
        if holiday_row is None:
            raise HTTPException(status_code=404, detail="Holiday not found")
        suggestions = conn.execute(
            """
            SELECT rs.*, c.name AS class_name, c.date AS scheduled_date
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
            start_date=date.fromisoformat(holiday_row["start_date"]),
            end_date=date.fromisoformat(holiday_row["end_date"]),
            academic_year_id=holiday_row["academic_year_id"],
            suggestions=[ReschedulingSuggestion(**dict(item)) for item in suggestions],
        )


@app.post("/holidays", response_model=HolidayResponse, status_code=status.HTTP_201_CREATED)
def create_holiday(payload: HolidayCreate) -> HolidayResponse:
    with database.connection_scope() as conn:
        _ensure_academic_year(conn, payload.academic_year_id)
        cursor = conn.execute(
            """
            INSERT INTO holidays (name, start_date, end_date, academic_year_id)
            VALUES (?, ?, ?, ?)
            """,
            (
                payload.name,
                payload.start_date.isoformat(),
                payload.end_date.isoformat(),
                payload.academic_year_id,
            ),
        )
        holiday_id = cursor.lastrowid
        suggestions = scheduler.recompute_for_holiday(conn, holiday_id)
        holiday_row = conn.execute(
            "SELECT * FROM holidays WHERE id = ?", (holiday_id,)
        ).fetchone()
        assert holiday_row is not None
        return HolidayResponse(
            id=holiday_row["id"],
            name=holiday_row["name"],
            start_date=date.fromisoformat(holiday_row["start_date"]),
            end_date=date.fromisoformat(holiday_row["end_date"]),
            academic_year_id=holiday_row["academic_year_id"],
            suggestions=[ReschedulingSuggestion(**item) for item in suggestions],
        )


@app.put("/holidays/{holiday_id}", response_model=HolidayResponse)
def update_holiday(holiday_id: int, payload: HolidayUpdate) -> HolidayResponse:
    with database.connection_scope() as conn:
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
                payload.start_date.isoformat(),
                payload.end_date.isoformat(),
                payload.academic_year_id,
                holiday_id,
            ),
        )
        suggestions = scheduler.recompute_for_holiday(conn, holiday_id)
        holiday_row = conn.execute(
            "SELECT * FROM holidays WHERE id = ?", (holiday_id,)
        ).fetchone()
        assert holiday_row is not None
        return HolidayResponse(
            id=holiday_row["id"],
            name=holiday_row["name"],
            start_date=date.fromisoformat(holiday_row["start_date"]),
            end_date=date.fromisoformat(holiday_row["end_date"]),
            academic_year_id=holiday_row["academic_year_id"],
            suggestions=[ReschedulingSuggestion(**item) for item in suggestions],
        )


@app.delete("/holidays/{holiday_id}")
def delete_holiday(holiday_id: int) -> dict[str, str]:
    with database.connection_scope() as conn:
        deleted = conn.execute(
            "DELETE FROM holidays WHERE id = ?", (holiday_id,)
        )
        if deleted.rowcount == 0:
            raise HTTPException(status_code=404, detail="Holiday not found")
    return {"status": "deleted"}


def _ensure_academic_year(conn: sqlite3.Connection, academic_year_id: int) -> None:
    year = conn.execute(
        "SELECT id FROM academic_years WHERE id = ?", (academic_year_id,)
    ).fetchone()
    if year is None:
        raise HTTPException(status_code=400, detail="Academic year not found")


def _load_class(conn: sqlite3.Connection, class_id: int) -> ClassResponse:
    class_row = conn.execute(
        "SELECT * FROM classes WHERE id = ?", (class_id,)
    ).fetchone()
    if class_row is None:
        raise HTTPException(status_code=404, detail="Class not found")

    group_row = conn.execute(
        "SELECT name FROM groups WHERE id = ?", (class_row["group_id"],)
    ).fetchone()
    group_name = group_row["name"] if group_row else ""

    suggestions_rows = conn.execute(
        """
        SELECT rs.*, c.name AS class_name, c.date AS scheduled_date
        FROM rescheduling_suggestions rs
        JOIN classes c ON c.id = rs.class_id
        WHERE rs.class_id = ?
        ORDER BY rs.id
        """,
        (class_id,),
    ).fetchall()

    suggestions = [ReschedulingSuggestion(**dict(row)) for row in suggestions_rows]
    return _row_to_class_response(class_row, group_name).model_copy(
        update={"suggestions": suggestions}
    )


__all__ = [
    "agenda_endpoint",
    "approve_plan_draft",
    "create_group",
    "create_holiday",
    "create_level",
    "delete_holiday",
    "generate_classes_endpoint",
    "get_class",
    "get_holiday",
    "get_plan_draft",
    "get_topic_report",
    "get_trimester_report",
    "ingest_endpoint",
    "list_academic_years",
    "list_classes",
    "list_holidays",
    "patch_plan_draft",
    "query_endpoint",
    "reparse_plan_draft",
    "serve_frontend",
    "update_class",
    "update_holiday",
]
